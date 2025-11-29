import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict
import time
from collections import namedtuple

Relationship = namedtuple(
    "Relationship", ["related_movie_id", "relationship_type", "movie_title"]
)


class KinopoiskRelationshipParser:
    def __init__(self):
        self.base_url = "https://www.kinopoisk.ru/film"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def get_relationships(self, movie_id: int) -> List[Relationship]:
        url = f"{self.base_url}/{movie_id}/other/"
        relationships = []

        try:
            response = self.session.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            relationship_headers = soup.find_all("td", class_="main_line")

            for header in relationship_headers:
                relationship_type = header.get_text(strip=True)

                items = []
                current = header.find_next()

                while current:
                    if (
                        current.name == "td"
                        and current.get("class")
                        and "main_line" in current.get("class", [])
                    ):
                        break

                    if (
                        current.name == "div"
                        and current.get("class")
                        and "item" in current.get("class", [])
                    ):
                        items.append(current)

                    current = current.find_next()

                for item in items:
                    links = item.find_all("a", href=re.compile(r"/(film|series)/\d+/"))

                    for link in links:
                        href = link.get("href")
                        if href:
                            match = re.search(r"/(?:film|series)/(\d+)/", href)
                            if match:
                                related_movie_id = match.group(1)
                                if related_movie_id != str(movie_id):
                                    movie_title = ""
                                    name_span = item.find("span", class_="name")

                                    if name_span:
                                        title_link = name_span.find("a")
                                        if title_link:
                                            movie_title = title_link.get_text(
                                                strip=True
                                            )
                                        else:
                                            movie_title = name_span.get_text(strip=True)

                                    if not movie_title:
                                        movie_title = link.get_text(strip=True)

                                    if not movie_title:
                                        movie_title = link.get("title", "").strip()

                                    if movie_title:
                                        relationship_data = Relationship(
                                            related_movie_id=related_movie_id,
                                            relationship_type=relationship_type,
                                            movie_title=movie_title,
                                        )
                                        relationships.append(relationship_data)

            unique_relationships = []
            seen = set()
            for rel in relationships:
                key = (rel.related_movie_id, rel.relationship_type)
                if key not in seen:
                    seen.add(key)
                    unique_relationships.append(rel)

            return unique_relationships

        except requests.RequestException as e:
            print(f"Error fetching page for movie ID {movie_id}: {e}")
            return []
        except Exception as e:
            print(f"Error parsing relationships for movie ID {movie_id}: {e}")
            return []

    def get_all_relationships_batch(
        self, movie_ids: List[int]
    ) -> Dict[int, List[Relationship]]:
        results = {}

        for movie_id in movie_ids:
            print(f"Parsing relationships for movie ID: {movie_id}")
            relationships = self.get_relationships(movie_id)
            results[movie_id] = relationships

            # уважим сервер и поставим дилей
            time.sleep(1)

        return results


def main():
    parser = KinopoiskRelationshipParser()
    movie_id = 687595
    relationships = parser.get_relationships(movie_id)

    print(f"Found {len(relationships)} relationships:")
    for rel in relationships:
        print(
            f"  - {rel.movie_title} ({rel.related_movie_id}) - {rel.relationship_type}"
        )


if __name__ == "__main__":
    main()
