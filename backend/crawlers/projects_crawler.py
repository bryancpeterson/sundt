import os
import json
import requests
from bs4 import BeautifulSoup
import time
import re

class SundtProjectsCrawler:
    # Base URLs for the crawler
    BASE_URL = "https://www.sundt.com"
    PROJECTS_URL = f"{BASE_URL}/projects/"
    AJAX_URL = f"{BASE_URL}/wp-json/facetwp/v1/refresh"  # FacetWP AJAX endpoint

    def __init__(self, output_file="data/projects.json"):
        self.output_file = output_file
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        # Setup request headers to mimic a browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": self.PROJECTS_URL  # Important for AJAX requests
        }
        # Track project URLs we've already seen to avoid duplicates
        self.seen_project_urls = set()

    def crawl(self):
        print(f"Crawling projects from {self.PROJECTS_URL}")
        projects = []

        try:
            # Step 1: Get the main projects page
            response = requests.get(self.PROJECTS_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract projects from the first page
            project_cards = soup.select(".project-card")
            print(f"Processing {len(project_cards)} projects from first page")

            for card in project_cards:
                project_data = self._extract_project_data(card)
                if project_data and project_data['url'] not in self.seen_project_urls:
                    self.seen_project_urls.add(project_data['url'])
                    projects.append(project_data)

            # Step 2: Extract FacetWP settings for pagination
            fwp_settings = self._extract_fwp_settings(response.text)

            # Step 3: Handle pagination based on whether we found FacetWP settings
            if not fwp_settings:
                # Fallback: Try direct pagination if FacetWP settings couldn't be extracted
                print("Could not extract FacetWP settings. Will try direct pagination approach.")
                page = 2
                max_attempts = 20  # Safety limit to prevent infinite loops

                while page <= max_attempts:
                    print(f"Trying direct page {page}...")
                    page_url = f"{self.PROJECTS_URL}page/{page}/"
                    try:
                        page_response = requests.get(page_url)
                        if page_response.status_code != 200:
                            print(f"Reached end of pagination at page {page}")
                            break

                        page_soup = BeautifulSoup(page_response.text, "html.parser")
                        page_cards = page_soup.select(".project-card")
                        if not page_cards:
                            print(f"No project cards found on page {page}")
                            break

                        print(f"Processing {len(page_cards)} projects from page {page}")
                        for card in page_cards:
                            project_data = self._extract_project_data(card)
                            if project_data and project_data['url'] not in self.seen_project_urls:
                                self.seen_project_urls.add(project_data['url'])
                                projects.append(project_data)

                        page += 1
                        time.sleep(1)  # Be nice to the server
                    except Exception as e:
                        print(f"Error loading page {page}: {e}")
                        break
            else:
                # Use AJAX pagination with FacetWP settings
                total_pages = fwp_settings.get('total_pages', 20)  # Default to 20 if not found
                print(f"Found FacetWP settings. Total pages estimated: {total_pages}")

                # Process remaining pages using AJAX
                for page in range(2, total_pages + 1):
                    print(f"Loading page {page} of {total_pages} via AJAX")
                    
                    # Create payload with correct FacetWP structure
                    payload = {
                        "action": "facetwp_refresh",
                        "data": {
                            "extras": {"selections": True, "sort": "default"},
                            "facets": {
                                "region": [], "project_delivery_methods": [],
                                "project_markets": [], "project_submarket": [], "count": []
                            },
                            "first_load": 0,
                            "frozen_facets": {},
                            "http_params": {"get": [], "uri": "projects", "url_vars": []},
                            "is_bfcache": 1,
                            "paged": page,  # Current page number
                            "soft_refresh": 1,
                            "template": "projects"
                        }
                    }

                    try:
                        # Make AJAX request to load more projects
                        ajax_response = requests.post(
                            self.AJAX_URL,
                            headers=self.headers,
                            json=payload
                        )

                        if ajax_response.status_code != 200:
                            print(f"Error loading page {page}: Status {ajax_response.status_code}")
                            print(f"Response: {ajax_response.text[:200]}...")  # Print start of response
                            continue

                        try:
                            # Parse AJAX response
                            ajax_data = ajax_response.json()
                            
                            # Check different possible response structures
                            html_content = (
                                ajax_data.get('template') or
                                ajax_data.get('html') or
                                ajax_data.get('content')
                            )

                            if not html_content:
                                print(f"No HTML content returned for page {page}")
                                print(f"Response keys: {ajax_data.keys()}")
                                continue

                            # Extract projects from AJAX response
                            ajax_soup = BeautifulSoup(html_content, "html.parser")
                            ajax_project_cards = ajax_soup.select(".project-card")
                            if not ajax_project_cards:
                                print(f"No project cards found in AJAX response for page {page}")
                                continue

                            print(f"Processing {len(ajax_project_cards)} projects from page {page}")
                            for card in ajax_project_cards:
                                project_data = self._extract_project_data(card)
                                if project_data and project_data['url'] not in self.seen_project_urls:
                                    self.seen_project_urls.add(project_data['url'])
                                    projects.append(project_data)
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON from AJAX response: {e}")
                            print(f"Response text: {ajax_response.text[:100]}...")
                    except Exception as e:
                        print(f"Error making AJAX request: {e}")

                    time.sleep(1)  # Be nice to the server

            # Step 4: Get detailed information for each project
            print(f"Getting detailed information for {len(projects)} projects...")
            for i, project in enumerate(projects):
                if 'url' in project and project['url']:
                    print(f"Processing project {i+1}/{len(projects)}: {project['title']}")
                    detailed_data = self._get_project_details(project['url'])
                    if detailed_data:
                        project.update(detailed_data)

                # Save intermediate results every 10 projects
                if (i + 1) % 10 == 0:
                    print(f"Processed {i + 1}/{len(projects)} project details")
                    self._save_data(projects)  # Checkpoint save

                time.sleep(0.5)  # Be nice to the server

        except Exception as e:
            print(f"Error crawling projects: {e}")

        # Final save of all data
        self._save_data(projects)
        print(f"Final count: {len(projects)} unique projects crawled")
        return projects

    def _extract_fwp_settings(self, html_content):
        """Extract FacetWP pagination settings from the HTML."""
        try:
            # Try multiple regex patterns to find FacetWP settings
            patterns = [
                r"window\.FWP_JSON\s*=\s*(\{.*?\});.*?window\.FWP_HTTP",
                r"var\s+FWP_JSON\s*=\s*(\{.*?\});",
                r"FWP\.preload_data\s*=\s*(\{.*?\});"
            ]

            for pattern in patterns:
                matches = re.search(pattern, html_content, re.DOTALL)
                if matches:
                    json_str = matches.group(1)
                    try:
                        data = json.loads(json_str)
                        # Try different JSON structures to find pagination info
                        if 'preload_data' in data and 'settings' in data['preload_data']:
                            return data['preload_data']['settings'].get('pager')
                        elif 'settings' in data and 'pager' in data['settings']:
                            return data['settings']['pager']
                        return data
                    except json.JSONDecodeError:
                        continue

            # Fallback: Look for total_pages directly in the HTML
            total_pages_match = re.search(r'total_pages["\']?\s*:\s*(\d+)', html_content)
            if total_pages_match:
                return {"total_pages": int(total_pages_match.group(1))}

            # Fallback: Look for pagination elements in the HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            pagination = soup.select('.pagination, .nav-links, .facetwp-pager')
            if pagination:
                page_links = pagination[0].select('a')
                highest_page = max([
                    int(link.get_text(strip=True))
                    for link in page_links
                    if link.get_text(strip=True).isdigit()
                ], default=1)
                return {"total_pages": highest_page}
        except Exception as e:
            print(f"Error extracting FacetWP settings: {e}")

        return None

    def _extract_project_data(self, card):
        """Extract basic project data from a project card element."""
        try:
            # Find the link element (multiple possible selectors)
            link_element = card.select_one("a.project-card__link, a.card-link, .project-card a, .project a")
            if not link_element:
                return None

            # Get the project URL and ensure it's absolute
            project_url = link_element.get("href")
            if project_url and not project_url.startswith(('http://', 'https://')):
                project_url = self.BASE_URL + project_url if not project_url.startswith('/') else self.BASE_URL + project_url

            # Get the project title
            title_element = card.select_one(".project-card__title, .card-title, h2, h3, .title")
            title_text = title_element.get_text(strip=True) if title_element else "Unknown Project"
            title = re.sub(r'▶|→|⇒', '', title_text).strip()  # Remove arrow symbols

            # Get the project image
            img_element = card.select_one(".project-card__image img, .card-img img, img")
            image_url = img_element.get("src") if img_element else ""
            if image_url and not image_url.startswith(('http://', 'https://')):
                image_url = self.BASE_URL + image_url if not image_url.startswith('/') else self.BASE_URL + image_url

            # Get any snippet/excerpt text
            snippet_element = card.select_one(".project-card__excerpt, .card-text, .excerpt, p")
            snippet = snippet_element.get_text(strip=True) if snippet_element else ""

            return {
                "title": title,
                "url": project_url,
                "image_url": image_url,
                "snippet": snippet
            }
        except Exception as e:
            print(f"Error extracting project data from card: {e}")
            return None

    def _get_project_details(self, project_url):
        """Get detailed project information from the project page."""
        try:
            full_url = project_url if project_url.startswith("http") else self.BASE_URL + project_url
            response = requests.get(full_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Initialize the detailed data structure
            detailed_data = {
                "metadata": {},  # Will hold location, client, value, etc.
                "impact": {},    # Will hold Community Impact section
                "overview": "",  # Will hold Project Overview text
                "features": []   # Will hold Features & Highlights
            }

            # Extract metadata from the list-info section
            metadata_items = soup.select(".list-info li")
            for item in metadata_items:
                label_elem = item.select_one("h5")
                value_elem = item.select_one("p")
                if label_elem and value_elem:
                    # Clean up the label for use as a key
                    label = label_elem.get_text(strip=True).rstrip(':').lower().replace(' ', '_')
                    value = value_elem.get_text(strip=True)
                    
                    # Handle specialties as a list (comma-separated)
                    if label == "specialties":
                        detailed_data["metadata"][label] = [s.strip() for s in value.split(',')]
                    else:
                        detailed_data["metadata"][label] = value

            # Extract the Community Impact section
            impact_section = soup.find("h5", string=lambda text: text and "Community Impact" in text)
            if impact_section:
                impact_container = impact_section.find_parent("div", class_="ModalContainer")
                if impact_container:
                    # Get the impact title
                    impact_title = impact_container.select_one("h3")
                    if impact_title:
                        detailed_data["impact"]["title"] = impact_title.get_text(strip=True)
                    
                    # Get the impact description
                    impact_desc = impact_container.select_one("p")
                    if impact_desc:
                        detailed_data["impact"]["description"] = impact_desc.get_text(strip=True)

            # Extract Project Overview
            overview_section = soup.find("h6", string=lambda text: text and "Project Overview" in text)
            if overview_section:
                overview_container = overview_section.find_parent("div", class_="section__content")
                if overview_container:
                    # Get all paragraphs in the overview section
                    overview_paragraphs = overview_container.select("p:not([id])")
                    overview_text = " ".join([p.get_text(strip=True) for p in overview_paragraphs])
                    
                    # Also get any collapsed content (Read More sections)
                    collapsed_content = overview_container.select(".content.collapse p")
                    if collapsed_content:
                        overview_text += " " + " ".join([p.get_text(strip=True) for p in collapsed_content])
                    
                    detailed_data["overview"] = overview_text

            # Extract Features & Highlights
            features_section = soup.find("h3", string=lambda text: text and "Features & Highlights" in text)
            if features_section:
                features_container = features_section.find_parent("div", class_="section__aside")
                if features_container:
                    # Get all bullet points
                    feature_items = features_container.select("ul.list-bullets li")
                    detailed_data["features"] = [item.get_text(strip=True) for item in feature_items]

            # Extract any testimonial/quote
            blockquote = soup.select_one("blockquote")
            if blockquote:
                quote_text = blockquote.get_text(strip=True)
                if quote_text:
                    detailed_data["testimonial"] = quote_text

            return detailed_data
        except Exception as e:
            print(f"Error getting project details from {project_url}: {e}")
            return {}

    def _save_data(self, projects):
        """Save the extracted project data to a JSON file."""
        try:
            # Process the projects to create a well-structured output
            processed_projects = process_projects(projects)
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump({"projects": processed_projects}, f, indent=2)
            print(f"Saved {len(processed_projects)} projects to {self.output_file}")
        except Exception as e:
            print(f"Error saving data: {e}")

def process_projects(projects):
    """Process the crawled projects to create a well-structured final output."""
    processed_projects = []

    for project in projects:
        # Start with basic project info
        processed_project = {
            "title": project.get("title", ""),
            "url": project.get("url", ""),
            "image_url": project.get("image_url", "")
        }

        # Add metadata as top-level fields
        if "metadata" in project:
            for key, value in project["metadata"].items():
                processed_project[key] = value

        # Add overview as description
        if "overview" in project and project["overview"]:
            processed_project["description"] = project["overview"]

        # Add impact section if available
        if "impact" in project and project["impact"]:
            processed_project["impact"] = project["impact"]

        # Add features if available
        if "features" in project and project["features"]:
            processed_project["features"] = project["features"]

        # Add testimonial if available
        if "testimonial" in project:
            processed_project["testimonial"] = project["testimonial"]

        processed_projects.append(processed_project)

    return processed_projects

if __name__ == "__main__":
    crawler = SundtProjectsCrawler()
    projects = crawler.crawl()
    print(f"Extracted {len(projects)} projects in total")