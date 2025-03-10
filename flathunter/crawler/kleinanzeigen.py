"""Expose crawler for Ebay Kleinanzeigen"""
import re
import datetime
from typing import Optional

from bs4 import Tag
from selenium.webdriver import Chrome

from flathunter.abstract_crawler import Crawler
from flathunter.chrome_wrapper import get_chrome_driver
from flathunter.exceptions import DriverLoadException
from flathunter.logging import logger

class Kleinanzeigen(Crawler):
    """Implementation of Crawler interface for Ebay Kleinanzeigen"""

    URL_PATTERN = re.compile(r'https://www\.kleinanzeigen\.de')
    MONTHS = {
        "Januar": "01",
        "Februar": "02",
        "März": "03",
        "April": "04",
        "Mai": "05",
        "Juni": "06",
        "Juli": "07",
        "August": "08",
        "September": "09",
        "Oktober": "10",
        "November": "11",
        "Dezember": "12"
    }

    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.driver = None


    def get_driver(self) -> Optional[Chrome]:
        """Lazy method to fetch the driver as required at runtime"""
        if self.driver is not None:
            return self.driver
        driver_arguments = self.config.captcha_driver_arguments()
        self.driver = get_chrome_driver(driver_arguments)
        return self.driver

    def get_driver_force(self) -> Chrome:
        """Fetch the driver, and throw an exception if it is not configured or available"""
        res = self.get_driver()
        if res is None:
            raise DriverLoadException("Unable to load chrome driver when expected")
        return res

    def get_page(self, search_url, driver=None, page_no=None):
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""
        return self.get_soup_from_url(search_url, driver=self.get_driver())

    def get_expose_details(self, expose):
        soup = self.get_page(expose['url'], self.get_driver())
        for detail in soup.find_all('li', {"class": "addetailslist--detail"}):
            if re.match(r'Verfügbar ab', detail.text):
                date_string = re.match(r'(\w+) (\d{4})', detail.text)
                if date_string is not None:
                    expose['from'] = "01." + self.MONTHS[date_string[1]] + "." + date_string[2]
        if 'from' not in expose:
            expose['from'] = datetime.datetime.now().strftime('%02d.%02m.%Y')
        return expose

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = []
        soup = soup.find(id="srchrslt-adtable")

        try:
            title_elements = soup.find_all(lambda e: e.has_attr('class')
                                           and 'ellipsis' in e['class'])
        except AttributeError:
            return entries

        expose_ids = soup.find_all("article", class_="aditem")

        for idx, title_el in enumerate(title_elements):
            try:
                price = expose_ids[idx].find(
                    class_="aditem-main--middle--price-shipping--price").text.strip()
                tags = expose_ids[idx].find_all(class_="simpletag")
                address = expose_ids[idx].find("div", {"class": "aditem-main--top--left"})
                image_element = expose_ids[idx].find("div", {"class": "galleryimage-element"})
            except AttributeError as error:
                logger.warning("Unable to process eBay expose: %s", str(error))
                continue

            if image_element is not None:
                image = image_element["data-imgsrc"]
            else:
                image = None

            address = address.text.strip()
            address = address.replace('\n', ' ').replace('\r', '')
            address = " ".join(address.split())

            rooms = ""
            if len(tags) > 1:
                rooms_match = re.match(r'(\d+)', tags[1].text)
                if rooms_match is not None:
                    rooms = rooms_match[1]

            try:
                size = tags[0].text
            except (IndexError, TypeError):
                size = ""
            details = {
                'id': int(expose_ids[idx].get("data-adid")),
                'image': image,
                'url': ("https://www.kleinanzeigen.de" + title_el.get("href")),
                'title': title_el.text.strip(),
                'price': price,
                'size': size,
                'rooms': rooms,
                'address': address,
                'crawler': self.get_name()
            }
            entries.append(details)

        logger.debug('Number of entries found: %d', len(entries))

        return entries

    def load_address(self, url):
        """Extract address from expose itself"""
        expose_soup = self.get_page(url)
        street_raw = ""
        street_el = expose_soup.find(id="street-address")
        if isinstance(street_el, Tag):
            street_raw = street_el.text
        address_raw = ""
        address_el = expose_soup.find(id="viewad-locality")
        if isinstance(address_el, Tag):
            address_raw = address_el.text

        return address_raw.strip().replace("\n", "") + " " + street_raw.strip()
