import datetime
import glob
import json
import os
import pkg_resources
import pytest
import yaml
from scrapy.http import Request, TextResponse
from misinformation.extractors import extract_article, extract_element, xpath_extract_spec, extract_datetime_string
from misinformation.extractors.extract_article import simplify_extracted_byline, simplify_extracted_title

SITE_TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "site_test_data")
UNIT_TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "unit_test_data")
SITE_CONFIG_FILE = pkg_resources.resource_string("misinformation", "../site_configs.yml")

# Load site-specific spider configurations
SITE_CONFIGS = yaml.load(SITE_CONFIG_FILE, Loader=yaml.FullLoader)
SITE_NAMES = sorted(SITE_CONFIGS.keys())


# ================= HELPER FUNCTIONS =================
def response_from_html_file(html_filepath):
    with open(html_filepath) as f:
        html = f.read()
    path_parts = os.path.split(html_filepath)
    filename = path_parts[-1]
    url = "http://{domain}/{path}".format(domain="example.com", path=filename)
    request = Request(url=url)
    response = TextResponse(url=url, body=html, encoding='utf-8', request=request)
    return response


def article_from_json_file(json_filepath):
    # Construct response from html
    with open(json_filepath) as f:
        article = json.loads(f.read())
    return article


def article_stems_for_site(site_name):
    # Find all HTML files in site test data directory
    html_file_paths = glob.glob(os.path.join(SITE_TEST_DATA_DIR, site_name, '*.html'))
    article_stems = []
    for html_file_path in html_file_paths:
        _, _file = os.path.split(html_file_path)
        article_stems.append(_file.split('_')[0])
    # Fail fixture set up if no test sites found for site
    assert article_stems != [], "No HTML test files found for site '{site}'".format(site=site_name)
    return article_stems


def article_infos_for_site(site_name):
    article_stems = article_stems_for_site(site_name)
    article_infos = [{"site_name": site_name, "article_stem": article_stem} for article_stem in article_stems]
    return article_infos


def article_infos_for_all_sites(site_names):
    article_infos = []
    for site_name in site_names:
        article_infos = article_infos + article_infos_for_site(site_name)
    return article_infos


def article_info_id(param):
    return "{site}/{article}".format(site=param['site_name'], article=param['article_stem'])


@pytest.fixture(params=article_infos_for_all_sites(SITE_NAMES), ids=article_info_id)
def article_info(request):
    return request.param


class MockDBEntry():
    def __init__(self, crawl_id, crawl_datetime):
        self.crawl_id = crawl_id
        self.crawl_datetime = datetime.datetime.strptime(crawl_datetime, '%Y-%m-%dT%H:%M:%S.%f%z')


# ================= TEST FUNCTIONS =================
def validate_extract_element(html, extract_spec, expected):
    actual = extract_element(html, extract_spec)
    # Ignore whitespace differences
    assert actual == expected or ''.join(actual.split()) == ''.join(expected.split())


def validate_extract_article(response, config, expected):
    article = extract_article(response, config)
    # Check title extraction
    assert article['title'] == expected['title']
    # Check byline extraction
    assert article['byline'] == expected['byline']
    # Check publication datetime extraction
    assert article['publication_datetime'] == expected['publication_datetime']
    # Check plain content extraction
    assert article['plain_content'] == expected['plain_content']
    # Check plain text extraction
    assert article['plain_text'] == expected['plain_text']


def test_extract_article_for_sites(article_info):
    # Select test config
    site_name = article_info['site_name']
    config = SITE_CONFIGS[site_name]

    # Define test file locations
    article_stem = article_info['article_stem']
    data_dir = os.path.join(SITE_TEST_DATA_DIR, site_name)
    html_filename = article_stem + '_article.html'
    json_filename = article_stem + '_extracted_data.json'
    html_filepath = os.path.join(data_dir, html_filename)
    json_filepath = os.path.join(data_dir, json_filename)

    # Load test data from files
    response = response_from_html_file(html_filepath)
    expected_article = article_from_json_file(json_filepath)

    # Test
    validate_extract_article(response, config, expected_article)


def test_extract_empty_article():
    # Mock response using expected article data
    html = "<html></html>"
    response = TextResponse(url="http://example.com", body=html, encoding="utf-8")

    # Mock config
    config_yaml = """
    site_name: 'example.com'
    article:
        title:
            select_method: 'xpath'
            select_expression: '//h1[@class="post-title"]/text()'
            match_rule: 'single'
        content:
            select_method: 'xpath'
            select_expression: '//p/text()'
            match_rule: 'first'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test single element extraction
    expected_content = None
    validate_extract_element(response, config['article']['content'], expected_content)


def test_extract_article_default():
    # Load test file
    html_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_article.html")
    response = response_from_html_file(html_filepath)
    # Load expected article data
    article_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_extracted_data_default.json")
    expected_article = article_from_json_file(article_filepath)

    # Mock config
    config_yaml = """
        site_name: 'example.com'
        start_url: 'http://addictinginfo.com/category/news/'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test
    article = extract_article(response, config)
    assert article == expected_article


def test_extract_article_default_with_crawl_info():
    # Load test file
    html_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_article.html")
    response = response_from_html_file(html_filepath)
    # Load expected article data
    article_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_extracted_data_default_with_crawl_info.json")
    expected_article = article_from_json_file(article_filepath)

    # Mock config
    config_yaml = """
        site_name: 'example.com'
        start_url: 'http://addictinginfo.com/category/news/'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Mock crawl info
    crawl_info = MockDBEntry(crawl_id="bdbcf1cf-e4,1f-4c10-9958-4ab1b07e46ae",
                             crawl_datetime="2018-10-17T20:25:34.234567+0000")

    # Test
    article = extract_article(response, config, crawl_info)
    assert article == expected_article


def test_extract_article_custom_title_selector():
    # Load test file
    html_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_article.html")
    response = response_from_html_file(html_filepath)
    # Load expected article data
    article_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_extracted_data_default_custom_title_selector.json")
    expected_article = article_from_json_file(article_filepath)

    # Mock config
    config_yaml = """
        site_name: 'example.com'
        article:
            title:
                select_method: 'xpath'
                select_expression: '//p[@id="test-custom-title"]/text()'
                match_rule: 'single'
            content:
                select_method: 'xpath'
                select_expression: '//div[@class="entry entry-content"]'
                match_rule: 'single'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test
    article = extract_article(response, config)
    assert article["title"] == expected_article["title"]


def test_extract_article_custom_byline_selector():
    # Load test file
    html_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_article.html")
    response = response_from_html_file(html_filepath)
    # Load expected article data
    article_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_extracted_data_default_custom_byline_selector.json")
    expected_article = article_from_json_file(article_filepath)

    # Mock config
    config_yaml = """
        site_name: 'example.com'
        article:
            byline:
                select_method: 'xpath'
                select_expression: '//p[@id="test-custom-byline"]/text()'
                match_rule: 'single'
            content:
                select_method: 'xpath'
                select_expression: '//div[@class="entry entry-content"]'
                match_rule: 'single'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test
    article = extract_article(response, config)
    assert article["byline"] == expected_article["byline"]


def test_extract_article_custom_content_selector():
    # Load test file
    html_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_article.html")
    response = response_from_html_file(html_filepath)
    # Load expected article data
    article_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_extracted_data_default_custom_content_selector.json")
    expected_article = article_from_json_file(article_filepath)

    # Mock config
    config_yaml = """
        site_name: 'example.com'
        article:
            content:
                select_method: 'xpath'
                select_expression: '//div[@class="entry entry-content"]'
                match_rule: 'single'

    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test
    article = extract_article(response, config)
    assert article["content"] == expected_article["content"]


def test_extract_article_custom_publication_datetime_selector():
    # Load test file
    html_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_article.html")
    response = response_from_html_file(html_filepath)
    # Load expected article data
    article_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_extracted_data_default_custom_publication_datetime_selector.json")
    expected_article = article_from_json_file(article_filepath)

    # Mock config
    config_yaml = """
        site_name: 'example.com'
        start_url: 'http://addictinginfo.com/category/news/'
        article:
            publication_datetime:
                select_method: 'xpath'
                select_expression: '//time[contains(concat(" ", normalize-space(@class), " "), " entry-date ")]/@datetime'
                match_rule: 'single'
            content:
                select_method: 'xpath'
                select_expression: '//div[@class="entry entry-content"]'
                match_rule: 'single'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test
    article = extract_article(response, config)
    assert article["publication_datetime"] == expected_article["publication_datetime"]


def test_extract_article_default_content_digests():
    # Load test file
    html_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_article.html")
    response = response_from_html_file(html_filepath)
    # Load expected article data
    article_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_extracted_data_default_content_digests.json")
    expected_article = article_from_json_file(article_filepath)

    # Mock config
    config_yaml = """
        site_name: 'example.com'
        start_url: 'http://addictinginfo.com/category/news/'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test
    article = extract_article(response, config, content_digests=True)
    assert article == expected_article


def test_extract_article_default_node_indexes():
    # Load test file
    html_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_article.html")
    response = response_from_html_file(html_filepath)
    # Load expected article data
    article_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_extracted_data_default_node_indexes.json")
    expected_article = article_from_json_file(article_filepath)

    # Mock config
    config_yaml = """
        site_name: 'example.com'
        start_url: 'http://addictinginfo.com/category/news/'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test
    article = extract_article(response, config, node_indexes=True)
    assert article == expected_article


def test_extract_article_default_content_digests_node_indexes():
    # Load test file
    html_filepath = os.path.join(UNIT_TEST_DATA_DIR, "addictinginfo.com-1_article.html")
    response = response_from_html_file(html_filepath)
    # Load expected article data
    article_filepath = os.path.join(UNIT_TEST_DATA_DIR,
                                    "addictinginfo.com-1_extracted_data_default_content_digests_node_indexes.json")
    expected_article = article_from_json_file(article_filepath)
    # Mock config
    config_yaml = """
        site_name: 'example.com'
        start_url: 'http://addictinginfo.com/category/news/'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test
    article = extract_article(response, config, content_digests=True, node_indexes=True)
    assert article == expected_article


def test_extract_element():
    # Mock response using expected article data
    html = """<html>
    <head></head>
    <body>
        <div class="post-content">
            <h1 class="post-title">Article title</h1>
            <div class="post-content">
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </div>
        </div>
    </body>
    </html>"""
    response = TextResponse(url="http://example.com", body=html, encoding="utf-8")

    # Mock config
    config_yaml = """
    site_name: 'example.com'
    article:
        title:
            select_method: 'xpath'
            select_expression: '//h1[@class="post-title"]/text()'
            match_rule: 'single'
        grouped-paragraphs:
            select_method: 'xpath'
            select_expression: '//p'
            match_rule: 'group'
        paragraphs:
            select_method: 'xpath'
            select_expression: '//p/text()'
            match_rule: 'all'
        first-paragraph:
            select_method: 'xpath'
            select_expression: '//p/text()'
            match_rule: 'first'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test single element extraction
    expected_title = "Article title"
    validate_extract_element(response, config['article']['title'], expected_title)
    # Test group element extraction
    expected_paragraphs = "<div><p>Paragraph 1</p><p>Paragraph 2</p><p>Paragraph 3</p></div>"
    validate_extract_element(response, config['article']['grouped-paragraphs'], expected_paragraphs)
    # Test all element extraction
    expected_paragraphs = ["Paragraph 1", "Paragraph 2", "Paragraph 3"]
    validate_extract_element(response, config['article']['paragraphs'], expected_paragraphs)
    # Test first element extraction
    expected_first_paragraph = "Paragraph 1"
    validate_extract_element(response, config['article']['first-paragraph'], expected_first_paragraph)


def test_remove_single_expression():
    # Mock response using expected article data
    html = """<html>
    <head></head>
    <body>
        <div class="post-content">
            <h1 class="post-title">Article title</h1>
            <div class="post-content">
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </div>
            <div class="social">
                <p>Twitter</p>
                <p>Facebook</p>
            </div>
        </div>
    </body>
    </html>"""
    response = TextResponse(url="http://example.com", body=html, encoding="utf-8")

    # Mock config
    config_yaml = """
    site_name: 'example.com'
    article:
        content:
            select_method: 'xpath'
            select_expression: '//div[@class="post-content"]'
            match_rule: 'first'
            remove_expressions:
                - '//div[@class="social"]'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test content extraction with removal
    expected_html = """
        <div class="post-content">
            <h1 class="post-title">Article title</h1>
            <div class="post-content">
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </div>
        </div>"""
    validate_extract_element(response, config['article']['content'], expected_html)


def test_remove_nested_expressions():
    # Mock response using expected article data
    html = """<html>
    <head></head>
    <body>
        <div class="post-content">
            <h1 class="post-title">Article title</h1>
            <div class="post-content">
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </div>
            <div class="social">
                <div class="social">
                    <p>Twitter</p>
                    <p>Facebook</p>
                </div>
            </div>
        </div>
    </body>
    </html>"""
    response = TextResponse(url="http://example.com", body=html, encoding="utf-8")

    # Mock config
    config_yaml = """
    site_name: 'example.com'
    article:
        content:
            select_method: 'xpath'
            select_expression: '//div[@class="post-content"]'
            match_rule: 'first'
            remove_expressions:
                - '//div[@class="social"]'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test content extraction with removal
    expected_html = """
        <div class="post-content">
            <h1 class="post-title">Article title</h1>
            <div class="post-content">
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </div>
        </div>"""
    validate_extract_element(response, config['article']['content'], expected_html)


def test_remove_multiple_nested_expressions():
    # Mock response using expected article data
    html = """<html>
    <head></head>
    <body>
        <div class="post-content">
            <h1 class="post-title">Article title</h1>
            <div class="post-content">
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </div>
            <div class="bad">
                <div class="social">
                    <p>Twitter</p>
                </div>
                <div class="social">
                    <div class="bad">
                        <p>Facebook</p>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>"""
    response = TextResponse(url="http://example.com", body=html, encoding="utf-8")

    # Mock config
    config_yaml = """
    site_name: 'example.com'
    article:
        content:
            select_method: 'xpath'
            select_expression: '//div[@class="post-content"]'
            match_rule: 'first'
            remove_expressions:
                - '//div[@class="social"]'
                - '//div[@class="bad"]'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test content extraction with removal
    expected_html = """
        <div class="post-content">
            <h1 class="post-title">Article title</h1>
            <div class="post-content">
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </div>
        </div>"""
    validate_extract_element(response, config['article']['content'], expected_html)


def test_remove_by_relative_path():
    # Mock response using expected article data
    html = """<html>
    <head></head>
    <body>
        <div class="post-content">
            <h1 class="post-title">Article title</h1>
            <div class="post-content">
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </div>
            <div class="social">
                <p>Twitter</p>
                <p>Facebook</p>
            </div>
        </div>
    </body>
    </html>"""
    response = TextResponse(url="http://example.com", body=html, encoding="utf-8")

    # Mock config
    config_yaml = """
    site_name: 'example.com'
    article:
        content:
            select_method: 'xpath'
            select_expression: '//div[@class="post-content"]'
            match_rule: 'first'
            remove_expressions:
                - '/div/div[@class="social"]'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    # Test content extraction with removal
    expected_html = """
        <div class="post-content">
            <h1 class="post-title">Article title</h1>
            <div class="post-content">
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
                <p>Paragraph 3</p>
            </div>
        </div>"""
    validate_extract_element(response, config['article']['content'], expected_html)


def test_xpath_extract_spec_default():
    expression = '//div[@class="content"]/a/text()'
    expected_extract_spec = {
        "select_method": "xpath",
        "select_expression": expression,
        "match_rule": "single",
        "warn_if_missing": True
    }
    extract_spec = xpath_extract_spec(expression)
    assert extract_spec == expected_extract_spec


def test_xpath_extract_spec_with_match_rule():
    expression = '//div[@class="content"]/a/text()'
    match_rule = "all"
    expected_extract_spec = {
        "select_method": "xpath",
        "select_expression": expression,
        "match_rule": match_rule,
        "warn_if_missing": True
    }
    extract_spec = xpath_extract_spec(expression, match_rule)
    assert extract_spec == expected_extract_spec


def test_extract_article_with_no_data_has_all_fields_present_but_null():
    # Mock response using expected article data
    html = """<html>
    <head></head>
    <body>
        <div>
            No article here.
        </div>
    </body>
    </html>"""
    response = TextResponse(url="http://example.com", body=html, encoding="utf-8")

    # Mock config
    config_yaml = """
    site_name: 'example.com'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    expected_article = {
        'site_name': "example.com",
        'article_url': "http://example.com",
        'title': None,
        'byline': None,
        'publication_datetime': None,
        'content': "<div>No article here.</div>",
        'plain_content': "<div>No article here.</div>",
        'plain_text': [{'text': 'No article here.'}],
        'metadata': None
    }

    # Test
    article = extract_article(response, config)
    assert article == expected_article


def test_extract_datetime_works_with_multiple_dates():
    # Mock response using expected article data
    html = """<html>
    <head></head>
    <body>
        <div class="subarticle">
            <p>October 22, 2018</p>
            <p>Article text here.</p>
            <p>May 15, 2006</p>
        </div>
    </body>
    </html>"""
    response = TextResponse(url="http://example.com", body=html, encoding="utf-8")

    # Mock config
    config_yaml = """
    site_name: 'example.com'
    article:
        publication_datetime:
            select_method: 'xpath'
            select_expression: '//div[@class="subarticle"]/p/text()'
            match_rule: 'comma_join'
            datetime_formats:
              - 'MMMM D YYYY'
        content:
            select_method: 'xpath'
            select_expression: '//div[@class="subarticle"]'
            match_rule: 'single'
    """
    config = yaml.load(config_yaml, Loader=yaml.FullLoader)

    expected_article = {
        'site_name': 'example.com',
        'article_url': 'http://example.com',
        'title': None,
        'byline': None,
        'publication_datetime': "2006-05-15T00:00:00",
        'content': '<div><p>October 22, 2018</p><p>Article text here.</p><p>May 15, 2006</p></div>',
        'plain_content': '<div><p>October 22, 2018</p><p>Article text here.</p><p>May 15, 2006</p></div>',
        'plain_text': [{"text": "October 22, 2018"}, {"text": "Article text here."}, {"text": "May 15, 2006"}],
        'metadata': None,
    }

    # Test
    article = extract_article(response, config)
    assert article == expected_article


def test_extract_datetime_iso8601_keep_timezone_keep():
    datetime_string = '2014-10-24T17:32:46+12:00'
    iso_string = extract_datetime_string(datetime_string, timezone=True)
    expected_iso_string = '2014-10-24T17:32:46+12:00'

    assert iso_string == expected_iso_string


def test_extract_datetime_iso8601_drop_timezone():
    datetime_string = '2014-10-24T17:32:46+12:00'
    iso_string = extract_datetime_string(datetime_string)
    expected_iso_string = '2014-10-24T17:32:46'

    assert iso_string == expected_iso_string


def test_extract_datetime_uk_format_without_timezone():
    datetime_string = '01/03/05'
    format_string = 'DD/MM/YY'
    iso_string = extract_datetime_string(datetime_string, format_string)
    expected_iso_string = '2005-03-01T00:00:00'

    assert iso_string == expected_iso_string


def test_extract_datetime_us_format_without_timezone():
    datetime_string = '03/01/05'
    format_string = 'MM/DD/YY'
    iso_string = extract_datetime_string(datetime_string, format_string)
    expected_iso_string = '2005-03-01T00:00:00'

    assert iso_string == expected_iso_string


def test_extract_datetime_byline_mmddyy_with_mmddyy_format():
    datetime_string = 'CHQ Staff | 10/17/18'
    format_string = 'MM/DD/YY'
    iso_string = extract_datetime_string(datetime_string, format_string)
    expected_iso_string = '2018-10-17T00:00:00'

    assert iso_string == expected_iso_string


def test_extract_datetime_byline_mmddyyyy_with_mmddyy_format():
    datetime_string = 'CHQ Staff | 10/17/2018'
    format_string = 'MM/DD/YY'
    iso_string = extract_datetime_string(datetime_string, format_string)
    expected_iso_string = '2018-10-17T00:00:00'

    assert iso_string == expected_iso_string


def test_extract_datetime_byline_mdyy_with_mdyy_format():
    datetime_string = 'CHQ Staff | 1/7/18'
    format_string = 'M/D/YY'
    iso_string = extract_datetime_string(datetime_string, format_string)
    expected_iso_string = '2018-01-07T00:00:00'

    assert iso_string == expected_iso_string


def test_extract_datetime_byline_0m0dyy_with_mdyy_format():
    datetime_string = 'CHQ Staff | 01/07/18'
    format_string = 'M/D/YY'
    iso_string = extract_datetime_string(datetime_string, format_string)
    expected_iso_string = '2018-01-07T00:00:00'

    assert iso_string == expected_iso_string


def test_extract_datetime_byline_mmddyy_with_mdyy_format():
    datetime_string = 'CHQ Staff | 12/17/18'
    format_string = 'M/D/YY'
    iso_string = extract_datetime_string(datetime_string, format_string)
    expected_iso_string = '2018-12-17T00:00:00'

    assert iso_string == expected_iso_string


@pytest.mark.parametrize("datetime_string, format_string, expected_iso_string", [
    ("PHOENIX, Ariz. — Oct 13, 2018, 6:42 PM ET", "MMM D YYYY h:mm A", "2018-10-13T18:42:00"),
    ("WASHINGTON, May 25, 2010 --", "MMMM DD YYYY", "2010-05-25T00:00:00"),
    ("KABUL, Afghanistan, Aug. 31, 2009", "MMM D YYYY", "2009-08-31T00:00:00"),
    ("ANCHORAGE, ALASKA, July 7, 2009", "MMMM D YYYY", "2009-07-07T00:00:00"),
    ("Feb 6, 2011", "MMM D YYYY", "2011-02-06T00:00:00"),
    ("WASHINGTON, April 19 , 2011", "MMMM DD YYYY", "2011-04-19T00:00:00"),
    ("Sept. 15, 2009", "MMM DD YYYY", "2009-09-15T00:00:00"),
    ("Feb.17, 2010", "MMM DD YYYY", "2010-02-17T00:00:00"),
    ("Jan., 27, 2010", "MMM DD YYYY", "2010-01-27T00:00:00"),
    ("July 2010", "MMMM YYYY", "2010-07-01T00:00:00"),
    ("2012-12-16", "YYYY-MM-DD", "2012-12-16T00:00:00"),
    ("July 8 ,2013", "MMMM D YYYY", "2013-07-08T00:00:00")
])
def test_extract_datetime_abcnews_variants(datetime_string, format_string, expected_iso_string):
    assert extract_datetime_string(datetime_string, format_string) == expected_iso_string


def test_simplify_extracted_byline():
    bylines = ["by Toby", "By Byram", "Toby and Byram", "and", "By", "Toby Man / AP News", "Ben Man (BBC)"]
    expected_bylines = ["Toby", "Byram", "Toby and Byram", "Toby Man", "Ben Man"]
    assert simplify_extracted_byline(bylines) == expected_bylines


def test_simplify_extracted_title():
    titles = ["Title | News site", "Title"]
    expected_titles = ["Title", "Title"]
    assert simplify_extracted_title(titles) == expected_titles
