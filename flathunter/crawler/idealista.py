"""Expose crawler for Idealista"""
import re

from flathunter.logging import logger
from typing import Optional, Any

from flathunter.abstract_crawler import Crawler
from selenium.webdriver import Chrome
from flathunter.exceptions import DriverLoadException
import requests
from flathunter.chrome_wrapper import get_chrome_driver
from bs4 import BeautifulSoup


class Idealista(Crawler):
    """Implementation of Crawler interface for Idealista"""

    URL_PATTERN = re.compile(r'https://www\.idealista\.com')

    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.driver = None

    # pylint: disable=unused-argument
    def get_page(self, search_url, driver=None, page_no=None):
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""

        return self.get_soup_from_url(search_url, driver=self.get_driver())

    def get_driver(self) -> Optional[Chrome]:
        """Lazy method to fetch the driver as required at runtime"""
        if self.driver is not None:
            return self.driver
        driver_arguments = self.config.captcha_driver_arguments()
        # driver_arguments.append("--proxy-server=http://161.22.42.104:3128")
        self.driver = get_chrome_driver(driver_arguments)
        return self.driver

    def get_driver_force(self) -> Chrome:
        """Fetch the driver, and throw an exception if it is not configured or available"""
        res = self.get_driver()
        if res is None:
            raise DriverLoadException("Unable to load chrome driver when expected")
        return res

    def get_soup_from_url(
            self,
            url: str,
            driver: Optional[Any] = None,
            checkbox: bool = False,
            afterlogin_string: Optional[str] = None) -> BeautifulSoup:
        """Creates a Soup object from the HTML at the provided URL"""

        logger.info("Fetching URL: %s", url)

        if driver is not None:
            logger.info("Using Selenium driver to fetch URL")
            driver.get(url)
            if re.search("captcha-delivery", driver.page_source):
                logger.info("Datadome captcha detected")
                self.resolve_datadome(
                    driver, checkbox, afterlogin_string or "")
            # вот тут надо правильные параметры передавать

            return BeautifulSoup(driver.page_source, 'lxml')

        logger.info("Using requests to fetch URL")
        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        if resp.status_code not in (200, 405):
            user_agent = 'Unknown'
            if 'User-Agent' in self.HEADERS:
                user_agent = self.HEADERS['User-Agent']
            logger.error("Got response k (%i): %s\n%s",
                         resp.status_code, resp.content, user_agent)

        return BeautifulSoup(resp.content, 'lxml')

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = []

        findings = soup.find_all('article', {"class": "item"})

        base_url = 'https://www.idealista.com'
        for row in findings:
            title_row = row.find('a', {"class": "item-link"})
            title = title_row.text.strip()
            url = base_url + title_row['href']
            picture_element = row.find('picture', {"class": "item-multimedia"})
            if "no-pictures" not in picture_element.get("class"):
                image = ""
            else:
                print(picture_element)
                image = picture_element.find('img')['src']

            # It's possible that not all three fields are present
            detail_items = row.find_all("span", {"class": "item-detail"})
            rooms = detail_items[0].text.strip() if (len(detail_items) >= 1) else ""
            size = detail_items[1].text.strip() if (len(detail_items) >= 2) else ""
            floor = detail_items[2].text.strip() if (len(detail_items) >= 3) else ""
            price = row.find("span", {"class": "item-price"}).text.strip().split("/")[0]

            details_title = (f"{title} - {floor}") if (len(floor) > 0) else title

            details = {
                'id': int(row.get("data-adid")),
                'image': image,
                'url': url,
                'title': details_title,
                'price': price,
                'size': size,
                'rooms': rooms,
                'address': re.findall(r'(?:\sen\s|\suna\s)(.*)$', title)[0],
                'crawler': self.get_name()
            }

            entries.append(details)

        logger.debug('Number of entries found: %d', len(entries))

        return entries
