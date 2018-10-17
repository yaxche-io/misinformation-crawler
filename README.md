# Misinformation crawler
Web crawler to collect snapshots of articles to web archive.

See [main project](https://github.com/alan-turing-institute/misinformation) for project board and issues.

Can currently crawl the following sites with configurations in `misinformation/site_configs.yml`
- addictinginfo.com
- conservativehq.com
- davidwolfe.com
- empirenews.net
- federalistpress.com
- gellerreport.com
- globalresearch.ca
- henrymakow.com
- madworldnews.com
- occupydemocrats.com
- palmerreport.com
- prisonplanet.com
- youngcons.com

Usage: `python crawl_all.py -n=<max_articles_per_site>` (limit is optional and all articles will be crawled if left off)

Crawled articles saved one file per site in `articles/`

Actual number of articles returned may be up to 16 higher due to number of parallel requests scrapy has open at any time

Several other sites have custom crawlers defined in `misinformation/spiders/spiders.py` that have not yet been
converted into configurations for the custom crawler. If scrapy is installed, these can be run using
`scrapy <spider-name>` (spider name is the website domain).

## Using pyodbc on macos
If you are not using the latest version of macos, you may get an "sql.h not found" error when installing the `pyodbc`
dependency via pip. This is because there is no compiled wheel for your version of macos. The options are (i) upgrade
to the latest version of macos or (ii) install the `unixodbc` driver libraries using `brew install unixodbc`.