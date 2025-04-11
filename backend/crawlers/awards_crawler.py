import os
import json
import requests
from bs4 import BeautifulSoup
import time
import re


class SundtAwardsCrawler:
    # Base URLs for the crawler
    BASE_URL = "https://www.sundt.com"
    AWARDS_URL = f"{BASE_URL}/about-us/awards-recognition/"

    def __init__(self, output_file="data/awards.json"):
        self.output_file = output_file
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        # Setup request headers to mimic a browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": self.AWARDS_URL
        }

    def crawl(self):
        print(f"Crawling awards from {self.AWARDS_URL}")
        awards = []

        try:
            # Step 1: Get the main awards page
            response = requests.get(self.AWARDS_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Step 2: Extract "New & Noteworthy" awards
            noteworthy_awards = self._extract_noteworthy_awards(soup)
            if noteworthy_awards:
                awards.extend(noteworthy_awards)
                print(f"Extracted {len(noteworthy_awards)} noteworthy awards")
            
            # Step 3: Extract "Additional Honors" awards (visible + hidden)
            additional_awards = self._extract_additional_honors(soup)
            if additional_awards:
                awards.extend(additional_awards)
                print(f"Extracted {len(additional_awards)} additional honors")
            
            # Step 4: Extract "News & Updates" awards
            news_awards = self._extract_news_updates(soup)
            if news_awards:
                awards.extend(news_awards)
                print(f"Extracted {len(news_awards)} news and updates")

        except Exception as e:
            print(f"Error crawling awards: {e}")

        # Save all data
        self._save_data(awards)
        print(f"Final count: {len(awards)} awards crawled")
        return awards

    def _extract_noteworthy_awards(self, soup):
        """Extract awards from the 'New & Noteworthy' section"""
        noteworthy_awards = []
        try:
            # Find the "New & Noteworthy" section
            noteworthy_section = soup.find("h4", class_="title-serif", string="New & Noteworthy")
            if not noteworthy_section:
                return noteworthy_awards
            
            # Find the container with the items
            items_container = noteworthy_section.find_parent("div", class_="section--cards")
            if not items_container:
                return noteworthy_awards
            
            # Find all award items
            award_items = items_container.select(".item")
            
            for item in award_items:
                # Extract title (header)
                title_elem = item.select_one(".item__head h3")
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # Extract description (body)
                desc_elem = item.select_one(".item__body p")
                description = desc_elem.get_text(strip=True) if desc_elem else ""
                
                # Extract icon/image if available
                img_elem = item.select_one(".item__image")
                image_url = ""
                if img_elem and "background-image" in img_elem.get("style", ""):
                    # Extract URL from background-image: url(...)
                    bg_img_match = re.search(r'url\((.*?)\)', img_elem.get("style", ""))
                    if bg_img_match:
                        image_url = bg_img_match.group(1).strip('\'"')
                        # Make relative URLs absolute
                        if image_url and not image_url.startswith(('http://', 'https://')):
                            image_url = self.BASE_URL + image_url if not image_url.startswith('/') else self.BASE_URL + image_url
                
                # Create award object
                award = {
                    "category": "New & Noteworthy",
                    "title": title,
                    "description": description,
                    "image_url": image_url
                }
                
                # Parse out award organization and date if possible
                if description:
                    # Try to extract organization and date from description
                    parts = description.split('/')
                    if len(parts) == 2:
                        award["organization"] = parts[0].strip()
                        award["date"] = parts[1].strip()
                    # If only one part, check if it's a date
                    elif len(parts) == 1 and re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b', description):
                        award["date"] = description.strip()
                
                noteworthy_awards.append(award)
                
        except Exception as e:
            print(f"Error extracting noteworthy awards: {e}")
            
        return noteworthy_awards

    def _extract_additional_honors(self, soup):
        """Extract awards from the 'Additional Honors' section, including hidden awards"""
        additional_awards = []
        try:
            # Find the "Additional Honors" section
            honors_section = soup.find("h5", class_="section__sub-title", string="Additional Honors")
            if not honors_section:
                return additional_awards
            
            # Find the container with the columns
            columns_container = honors_section.find_parent("div", class_="awardsSection")
            if not columns_container:
                return additional_awards
            
            # Process visible and hidden awards from both columns
            for column in columns_container.select(".col"):
                # Process visible awards in this column
                visible_awards = self._parse_awards_from_column(column, exclude_hidden=True)
                additional_awards.extend(visible_awards)
                
                # Process hidden awards in this column (those in div with class "hidden")
                hidden_div = column.select_one(".hidden")
                if hidden_div:
                    hidden_awards = self._parse_awards_from_column(hidden_div, exclude_hidden=False)
                    additional_awards.extend(hidden_awards)
                
        except Exception as e:
            print(f"Error extracting additional honors: {e}")
            
        return additional_awards
    
    def _parse_awards_from_column(self, column, exclude_hidden=False):
        """Parse award entries from a column in the Additional Honors section"""
        awards = []
        
        # Skip processing if this is a hidden div and we want to exclude hidden content
        if exclude_hidden and "hidden" in column.get("class", []):
            return awards
        
        # Group content by award entries
        # Each award typically has an h6 header followed by p tags
        current_award = None
        
        for elem in column.find_all(["h6", "p"]):
            # Skip if this element is within a hidden div and we want to exclude hidden
            if exclude_hidden and elem.find_parent(class_="hidden"):
                continue
                
            if elem.name == "h6":
                # Save previous award if exists
                if current_award:
                    awards.append(current_award)
                
                # Start a new award
                current_award = {
                    "category": "Additional Honors",
                    "award_type": elem.get_text(strip=True).replace("<em>", "").replace("</em>", "")
                }
            elif elem.name == "p" and current_award:
                # Add content to the current award
                content = elem.get_text(strip=True)
                
                # First p tag after h6 is usually the organization
                if "organization" not in current_award:
                    strong_elem = elem.find("strong")
                    if strong_elem:
                        current_award["organization"] = strong_elem.get_text(strip=True)
                        
                        # Remove organization from content for description
                        content = content.replace(current_award["organization"], "").strip()
                    
                # Check if there's a project link
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
                
                # Add remaining content as description
                if content and content != current_award.get("organization", ""):
                    if "description" not in current_award:
                        current_award["description"] = content
                    else:
                        current_award["description"] += " " + content
        
        # Don't forget to add the last award
        if current_award:
            awards.append(current_award)
            
        # Process descriptions to extract location and year
        for award in awards:
            if "description" in award:
                # Try to extract location (usually at the end before the year)
                location_match = re.search(r'([A-Za-z\s]+),\s*([A-Z]{2})\s*\d{4}', award["description"])
                if location_match:
                    award["location"] = f"{location_match.group(1)}, {location_match.group(2)}".strip()
                
                # Try to extract year (usually a 4-digit number at the end)
                year_match = re.search(r'\b(20\d{2})\b', award["description"])
                if year_match:
                    award["year"] = year_match.group(1)
        
        return awards

    def _extract_news_updates(self, soup):
        """Extract awards from the 'News & Updates' section"""
        news_awards = []
        try:
            # Find the "News & Updates" section
            news_section = soup.find("h5", class_="section__sub-title", string="News & Updates")
            if not news_section:
                return news_awards
            
            # Find the container with the slider
            slider_container = news_section.find_parent("div", class_="section--card-slider")
            if not slider_container:
                return news_awards
            
            # Find all slides
            slides = slider_container.select(".slider__slide")
            
            for slide in slides:
                # Extract card content
                card = slide.select_one(".card")
                if not card:
                    continue
                
                # Extract link
                link_elem = card.select_one("a")
                link = link_elem.get("href") if link_elem else ""
                if link and not link.startswith(('http://', 'https://')):
                    link = self.BASE_URL + link if not link.startswith('/') else self.BASE_URL + link
                
                # Extract title
                title_elem = card.select_one("h4")
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # Extract description
                desc_elem = card.select_one(".card-body")
                description = ""
                if desc_elem:
                    # Get text excluding the title
                    desc_text = desc_elem.get_text(strip=True)
                    if title in desc_text:
                        description = desc_text.replace(title, "").strip()
                    else:
                        description = desc_text
                
                # Extract image
                img_elem = card.select_one(".card-image")
                image_url = ""
                if img_elem and "background-image" in img_elem.get("style", ""):
                    # Extract URL from background-image: url(...)
                    bg_img_match = re.search(r'url\((.*?)\)', img_elem.get("style", ""))
                    if bg_img_match:
                        image_url = bg_img_match.group(1).strip('\'"')
                        # Make relative URLs absolute
                        if image_url and not image_url.startswith(('http://', 'https://')):
                            image_url = self.BASE_URL + image_url if not image_url.startswith('/') else self.BASE_URL + image_url
                
                # Create news award object
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
        """Save the extracted award data to a JSON file."""
        try:
            # Process the awards to create a well-structured output
            processed_awards = process_awards(awards)
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump({"awards": processed_awards}, f, indent=2)
            print(f"Saved {len(processed_awards)} awards to {self.output_file}")
        except Exception as e:
            print(f"Error saving data: {e}")

def process_awards(awards):
    """Process the crawled awards to create a well-structured final output."""
    processed_awards = []

    for award in awards:
        # Start with a clean award object
        processed_award = {
            "category": award.get("category", ""),
            "title": award.get("title", award.get("award_type", ""))
        }
        
        # Add organization if available
        if "organization" in award:
            processed_award["organization"] = award["organization"]
            
        # Add description if available
        if "description" in award:
            processed_award["description"] = award["description"]
            
        # Add location if available
        if "location" in award:
            processed_award["location"] = award["location"]
            
        # Add date/year if available
        if "date" in award:
            processed_award["date"] = award["date"]
        elif "year" in award:
            processed_award["year"] = award["year"]
            
        # Add image if available
        if "image_url" in award and award["image_url"]:
            processed_award["image_url"] = award["image_url"]
            
        # Add URL if available
        if "url" in award and award["url"]:
            processed_award["url"] = award["url"]
            
        # Add projects if available
        if "projects" in award and award["projects"]:
            processed_award["projects"] = award["projects"]
        
        processed_awards.append(processed_award)

    return processed_awards

if __name__ == "__main__":
    crawler = SundtAwardsCrawler()
    awards = crawler.crawl()
    print(f"Extracted {len(awards)} awards in total")