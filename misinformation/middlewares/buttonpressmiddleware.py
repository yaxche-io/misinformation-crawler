from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException, ElementNotVisibleException, ElementNotInteractableException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.expected_conditions import visibility_of_element_located, element_to_be_clickable
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains


class PressableButton:
    """Button class with attributes required by the ButtonPressMiddleware"""
    def __init__(self, xpath, interact_method):
        self.xpath = xpath
        self.interact_method = interact_method
        self.button = None

    def get_button(self, driver):
        """Use a webdriver to get an interactable button specified by the xpath"""
        self.button = driver.find_element_by_xpath(self.xpath)

    def press_button(self, driver):
        """Navigate to and press a button, using a webdriver"""
        self.get_button(driver)
        if self.interact_method == 'Return':
            # Interact by sending a keypress of 'Return' to the button. 
            # This works even when the button is not currently visible in the viewport.
            self.button.send_keys(Keys.RETURN)
        if self.interact_method == 'Click':
            # Interact by moving to the element and then clicking.
            # This is more fragile, so we only use it for those button
            # xpaths that will not accept keypress 'Return'.
            actions = ActionChains(driver)
            actions.move_to_element(self.button).perform()
            self.button.click()


class ButtonPressMiddleware:
    """Scrapy middleware to bypass 'load more' and form buttons using selenium.

    Buttons are identified by searching for XPath patterns.

    Selenium will first press each form button encountered.

    Selenium will then keep pressing any load button present until one of the following occurs:
        1. The button disappears (eg. when there are no more articles to load)
        2. The page takes too long to load (currently 60s)
        3. A maximum number of button presses is reached (currently 10000)
    """
    def __init__(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        self.driver = webdriver.Chrome(chrome_options=chrome_options)
        self.seen_urls = set()
        self.timeout = 60
        self.max_button_clicks = 10000
        self.form_buttons = [
            PressableButton('//input[contains(@class, "agree")]', 'Return'),
            PressableButton('//button[@name="agree"]', 'Return'),
            PressableButton('//button[@class="qc-cmp-button"]', 'Return'),
            PressableButton('//form[@class="gdpr-form"]/input[@class="btn"]', 'Return'),
            PressableButton('//button[contains(@class, "gdpr-modal-close")]', 'Return'),
        ]
        self.load_buttons = [
            PressableButton('//a[@class="load-more"]', 'Return'),
            PressableButton('//a[contains(@class, "m-more")]', 'Return'),
            PressableButton('//button[@class="btn-more"]', 'Return'),
            PressableButton('//button[text()="Show More"]', 'Return'),
            PressableButton('//button[text()="Load More"]', 'Return'),
            PressableButton('//button[contains(@class, "show-more")]', 'Return'),
            PressableButton('//button[@phx-track-id="load more"]', 'Return'),
            PressableButton('//div[contains(@class, "load-btn")]/a', 'Return'),
            PressableButton('//div[contains(@class, "button-load-more")]', 'Click'),
            PressableButton('//div[contains(@class, "pb-loadmore")]', 'Click'),
            PressableButton('//ul[contains(@class, "pager-load-more")]/li/a', 'Return'),
            PressableButton('//a[text()="Show More"]', 'Return'),
        ]

    def get_first_button_to_press(self, button_list):
        """Find the first button on the page from a list of PressableButton objects"""
        for button in button_list:
            try:
                button.get_button(self.driver)
                return button
            except WebDriverException:
                pass
        return None

    def response_contains_a_button(self, response):
        """Check if any there are any load or form buttons in the response."""
        for button in (self.load_buttons + self.form_buttons):
            if response.xpath(button.xpath):
                return True
        return False

    def response_contains_load_button(self, response):
        """Check if any there are any load buttons in the response."""
        for button in self.load_buttons:
            if response.xpath(button.xpath):
                return True
        return False

    def perform_button_pressing(self, button_to_press, button_list, spider, button_type='load'):
        """Press a button as many times as we want, catch exceptions and log info to spider"""
        n_clicks_performed = 0
        cached_page_source = None
        while True:
            try:
                # We need a nested try block here, since the WebDriverWait
                # inside the ElementNotVisibleException or the
                # ElementNotInteractableException can throw a
                # TimeoutException that we want to handle in the same way as
                # other TimeoutExceptions
                try:
                    # Cache the page source in case the page crashes
                    cached_page_source = self.driver.page_source

                    # Press a button
                    if button_type == 'load':
                        button_to_press.press_button(self.driver)
                    if button_type == 'form':
                        try:
                            button_to_press.press_button(self.driver)
                        # Stop trying to click a form button when it no longer exists
                        except (NoSuchElementException, ElementNotInteractableException):
                            break
                    # Store the button location so that we can check when the page is reloaded
                    button_location = button_to_press.button.location

                    # Track the number of clicks that we've performed
                    n_clicks_performed += 1
                    spider.logger.info('Clicked a load or form button once ({} times in total).'.format(n_clicks_performed))

                    # Terminate if we're at the maximum number of clicks
                    # We should only get that far for load buttons
                    if n_clicks_performed >= self.max_button_clicks > 0 and button_type == 'load':
                        spider.logger.info('Finished loading more articles after clicking button {} times.'.format(n_clicks_performed))
                        break

                    # Wait until the page has been refreshed. We test for this
                    # by checking whether the button has moved location.
                    # NB. the default poll frequency is 0.5s so if we want
                    # short timeouts this needs to be changed in the
                    # WebDriverWait constructor
                    WebDriverWait(self.driver, self.timeout).until(lambda _: button_location != button_to_press.button.location)

                except ElementNotVisibleException:
                    print(button_to_press.xpath, "ElementNotVisibleException")
                    # This can happen when the page refresh makes a previously
                    # found element invisible until the page load is finished
                    WebDriverWait(self.driver, self.timeout).until(visibility_of_element_located((By.XPATH, button_to_press.xpath)))
                except ElementNotInteractableException:
                    # This can happen when the page refresh makes an element
                    # non-clickable for some period
                    WebDriverWait(self.driver, self.timeout).until(element_to_be_clickable((By.XPATH, button_to_press.xpath)))
            except (NoSuchElementException, StaleElementReferenceException):
                # If there are still available buttons from the list on the page then repeat
                if self.get_first_button_to_press(button_list):
                    continue
                else:
                    spider.logger.info('Terminating button clicking since there are no more {} buttons on the page.'.format(button_type))
                    break
            except TimeoutException:
                spider.logger.info('Terminating button clicking after exceeding timeout of {} seconds.'.format(self.timeout))
                break
            except WebDriverException:
                spider.logger.info('Terminating button clicking after losing connection to the page.')
                break

        return cached_page_source

    def press_form_buttons(self, spider):
        """Press any form buttons on the page until the form dissapears"""
        for button in self.form_buttons:
            self.perform_button_pressing(button, self.form_buttons, spider, button_type='form')

    def process_response(self, request, response, spider):
        """Process the page response using the selenium driver if applicable.

        As the selenium driver is much slower than the the normal scrapy crawl,
        we only do this if we actively identify the page as having a javascript
        load button.
        """
        # Do not process the same request URL twice
        if request.url in self.seen_urls:
            return response
        self.seen_urls.add(request.url)

        # Look for a load button or form button using xpaths on the scrapy response
        if not self.response_contains_a_button(response):
            return response

        # Load the URL using chromedriver
        self.driver.get(request.url)

        # We should only reach this point if we have found a javascript button
        spider.logger.info('Identified a javascript load button on {}.'.format(request.url))

        # Press any form buttons needed to access the home page of the site
        self.press_form_buttons(spider)

        # Get the cached page source in case the page crashes
        if self.response_contains_load_button(response):
            cached_page_source = self.perform_button_pressing(self.get_first_button_to_press(self.load_buttons), self.load_buttons, spider)
        else:
            cached_page_source = self.driver.page_source

        # Get appropriately encoded HTML from the page
        try:
            html_str = self.driver.page_source.encode(request.encoding)
        except WebDriverException:
            html_str = cached_page_source.encode(request.encoding)

        # Add any cookies that we may have collected to the spider so that they
        # can be used for future requests
        spider.update_cookies(self.driver.get_cookies())
        return HtmlResponse(body=html_str, url=request.url, encoding=request.encoding, request=request)

    def spider_closed(self):
        """Shutdown the driver when spider is closed"""
        self.driver.quit()
