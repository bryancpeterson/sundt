import os
import json
import requests
from bs4 import BeautifulSoup
import time
import re


class SundtAwardsCrawler:
    BASE_URL = "https://www.sundt.com"
    AWARDS_URL = f"{BASE_URL}/about-us/awards-recognition/"

    def __init__(self, output_file="data/awards.json"):
        self.output_file = output_file
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        # Standard browser headers to avoid getting blocked
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": self.AWARDS_URL
        }

    def crawl(self):
        print(f"Crawling awards from {self.AWARDS_URL}")
        awards = []  # Will collect all awards from different sections

        try:
            response = requests.get(self.AWARDS_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract from each section of the awards page
            noteworthy_awards = self._extract_noteworthy_awards(soup)
            if noteworthy_awards:
                awards.extend(noteworthy_awards)
                print(f"Extracted {len(noteworthy_awards)} noteworthy awards")

            additional_awards = self._extract_additional_honors(soup)
            if additional_awards:
                awards.extend(additional_awards)
                print(f"Extracted {len(additional_awards)} additional honors")

            news_awards = self._extract_news_updates(soup)
            if news_awards:
                awards.extend(news_awards)
                print(f"Extracted {len(news_awards)} news and updates")

        except Exception as e:
            print(f"Error crawling awards: {e}")

        self._save_data(awards)
        print(f"Final count: {len(awards)} awards crawled")
        return awards

    def _extract_noteworthy_awards(self, soup):
        noteworthy_awards = []
        try:
            section = soup.find("h4", class_="title-serif", string="New & Noteworthy")
            if not section:
                return noteworthy_awards

            items_container = section.find_parent("div", class_="section--cards")
            if not items_container:
                return noteworthy_awards

            for item in items_container.select(".item"):
                title_elem = item.select_one(".item__head h3")
                title = title_elem.get_text(strip=True) if title_elem else ""

                desc_elem = item.select_one(".item__body p")
                description = desc_elem.get_text(strip=True) if desc_elem else ""

                # Check for background images in the CSS style attribute
                image_url = ""
                img_elem = item.select_one(".item__image")
                if img_elem and "background-image" in img_elem.get("style", ""):
                    bg_img_match = re.search(r'url\((.*?)\)', img_elem.get("style", ""))
                    if bg_img_match:
                        image_url = bg_img_match.group(1).strip('\'"')
                        if image_url and not image_url.startswith(('http://', 'https://')):
                            image_url = self.BASE_URL + image_url if not image_url.startswith('/') else self.BASE_URL + image_url

                award = {
                    "category": "New & Noteworthy",
                    "title": title,
                    "description": description,
                    "image_url": image_url
                }

                # Try to parse organization and date from description text
                if description:
                    parts = description.split('/')
                    if len(parts) == 2:
                        award["organization"] = parts[0].strip()
                        award["date"] = parts[1].strip()
                    elif len(parts) == 1 and re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b', description):
                        award["date"] = description.strip()

                noteworthy_awards.append(award)

        except Exception as e:
            print(f"Error extracting noteworthy awards: {e}")

        return noteworthy_awards

    def _extract_additional_honors(self, soup):
        additional_awards = []
        try:
            section = soup.find("h5", class_="section__sub-title", string="Additional Honors")
            if not section:
                return additional_awards

            container = section.find_parent("div", class_="awardsSection")
            if not container:
                return additional_awards

            # Process both visible and hidden awards in each column
            for column in container.select(".col"):
                visible_awards = self._parse_awards_from_column(column, exclude_hidden=True)
                additional_awards.extend(visible_awards)

                # Some awards are hidden behind "show more" functionality
                hidden_div = column.select_one(".hidden")
                if hidden_div:
                    hidden_awards = self._parse_awards_from_column(hidden_div, exclude_hidden=False)
                    additional_awards.extend(hidden_awards)

        except Exception as e:
            print(f"Error extracting additional honors: {e}")

        return additional_awards

    def _parse_awards_from_column(self, column, exclude_hidden=False):
        awards = []

        if exclude_hidden and "hidden" in column.get("class", []):
            return awards

        current_award = None

        # Awards are structured as h6 headers followed by p tags
        for elem in column.find_all(["h6", "p"]):
            if exclude_hidden and elem.find_parent(class_="hidden"):
                continue

            if elem.name == "h6":
                # Save the previous award before starting a new one
                if current_award:
                    awards.append(current_award)

                current_award = {
                    "category": "Additional Honors",
                    "award_type": elem.get_text(strip=True).replace("<em>", "").replace("</em>", "")
                }
            elif elem.name == "p" and current_award:
                content = elem.get_text(strip=True)

                # First strong tag usually contains the organization name
                if "organization" not in current_award:
                    strong_elem = elem.find("strong")
                    if strong_elem:
                        current_award["organization"] = strong_elem.get_text(strip=True)
                        content = content.replace(current_award["organization"], "").strip()

                # Look for any project links embedded in this paragraph
                link_elem = elem.find("a")
                if link_elem:
                    project_url = link_elem.get("href")
                    project_title = link_elem.get_text(strip=True)

                    if "projects" not in current_award:
                        current_award["projects"] = []

                    current_award["projects"].append({
                        "title": project_title,
                        "url": project_url if project_url.startswith(('http://', 'https://')) else self.BASE_URL + project_url if not project_url.startswith('/') else self.BASE_URL + project_url
                    })

                # Build up the description from remaining content
                if content and content != current_award.get("organization", ""):
                    if "description" not in current_award:
                        current_award["description"] = content
                    else:
                        current_award["description"] += " " + content

        # Don't forget the last award in the column
        if current_award:
            awards.append(current_award)

        # Extract location and year info from descriptions
        for award in awards:
            if "description" in award:
                location_match = re.search(r'([A-Za-z\s]+),\s*([A-Z]{2})\s*\d{4}', award["description"])
                if location_match:
                    award["location"] = f"{location_match.group(1)}, {location_match.group(2)}".strip()

                year_match = re.search(r'\b(20\d{2})\b', award["description"])
                if year_match:
                    award["year"] = year_match.group(1)

        return awards

    def _extract_news_updates(self, soup):
        news_awards = []
        try:
            section = soup.find("h5", class_="section__sub-title", string="News & Updates")
            if not section:
                return news_awards

            container = section.find_parent("div", class_="section--card-slider")
            if not container:
                return news_awards

            # Process each slide in the news carousel
            for slide in container.select(".slider__slide"):
                card = slide.select_one(".card")
                if not card:
                    continue

                link_elem = card.select_one("a")
                link = link_elem.get("href") if link_elem else ""
                if link and not link.startswith(('http://', 'https://')):
                    link = self.BASE_URL + link if not link.startswith('/') else self.BASE_URL + link

                title_elem = card.select_one("h4")
                title = title_elem.get_text(strip=True) if title_elem else ""

                desc_elem = card.select_one(".card-body")
                description = ""
                if desc_elem:
                    desc_text = desc_elem.get_text(strip=True)
                    # Remove title from description if it's duplicated
                    if title in desc_text:
                        description = desc_text.replace(title, "").strip()
                    else:
                        description = desc_text

                image_url = ""
                img_elem = card.select_one(".card-image")
                if img_elem and "background-image" in img_elem.get("style", ""):
                    bg_img_match = re.search(r'url\((.*?)\)', img_elem.get("style", ""))
                    if bg_img_match:
                        image_url = bg_img_match.group(1).strip('\'"')
                        if image_url and not image_url.startswith(('http://', 'https://')):
                            image_url = self.BASE_URL + image_url if not image_url.startswith('/') else self.BASE_URL + image_url

                news_award = {
                    "category": "News & Updates",
                    "title": title,
                    "description": description,
                    "url": link,
                    "image_url": image_url
                }

                news_awards.append(news_award)

        except Exception as e:
            print(f"Error extracting news updates: {e}")

        return news_awards

    def _save_data(self, awards):
        try:
            processed_awards = process_awards(awards)
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump({"awards": processed_awards}, f, indent=2)
            print(f"Saved {len(processed_awards)} awards to {self.output_file}")
        except Exception as e:
            print(f"Error saving data: {e}")

def process_awards(awards):
    """Clean up and standardize the award data structure"""
    processed_awards = []

    for award in awards:
        processed_award = {
            "category": award.get("category", ""),
            "title": award.get("title", award.get("award_type", ""))
        }

        # Add optional fields if they exist
        for field in ["organization", "description", "location", "image_url", "url", "projects"]:
            if field in award and award[field]:
                processed_award[field] = award[field]

        # Handle date/year fields
        if "date" in award:
            processed_award["date"] = award["date"]
        elif "year" in award:
            processed_award["year"] = award["year"]

        processed_awards.append(processed_award)

    return processed_awards

if __name__ == "__main__":
    crawler = SundtAwardsCrawler()
    awards = crawler.crawl()
    print(f"Extracted {len(awards)} awards in total")