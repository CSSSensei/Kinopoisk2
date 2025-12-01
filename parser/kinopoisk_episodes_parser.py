import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Optional
import time
from dataclasses import dataclass
from datetime import datetime, date


@dataclass
class EpisodeInfo:
    season_number: int
    episode_number: int
    title: str
    release_date: Optional[date] = None  # Use date object instead of string
    description: Optional[str] = None
    original_title: Optional[str] = None


@dataclass
class SeasonInfo:
    season_number: int
    release_year: Optional[int] = None


class KinopoiskEpisodesParser:
    def __init__(self):
        self.base_url = "https://www.kinopoisk.ru/film"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def get_episodes_and_seasons(self, movie_id: int) -> Dict[str, List]:
        url = f"{self.base_url}/{movie_id}/episodes"
        seasons = []
        episodes = []

        try:
            response = self.session.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            seasons_data, episodes_data = self._parse_seasons_and_episodes(soup)
            seasons.extend(seasons_data)
            episodes.extend(episodes_data)

            seen_seasons = set()
            unique_seasons = []
            for season in seasons:
                if season.season_number not in seen_seasons:
                    seen_seasons.add(season.season_number)
                    unique_seasons.append(season)
            seasons = unique_seasons

            return {"seasons": seasons, "episodes": episodes}

        except requests.RequestException as e:
            print(f"Error fetching page for movie ID {movie_id}: {e}")
            return {"seasons": [], "episodes": []}
        except Exception as e:
            print(f"Error parsing episodes for movie ID {movie_id}: {e}")
            return {"seasons": [], "episodes": []}

    def _parse_seasons_and_episodes(
        self, soup: BeautifulSoup
    ) -> tuple[List[SeasonInfo], List[EpisodeInfo]]:
        """Parse seasons and episodes information from the page."""
        seasons = []
        episodes = []

        episode_tables = soup.find_all("table")

        valid_season_tables = []

        for table in episode_tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            first_row_text = rows[0].get_text(strip=True)
            season_year_match = re.search(
                r"[Сс]езон\s+(\d+)\s*(\d{4}),\s*[Ээ]пизодов:\s*(\d+)", first_row_text
            )

            if season_year_match:
                season_number = int(season_year_match.group(1))
                release_year = int(season_year_match.group(2))
                episode_count = int(season_year_match.group(3))

                actual_episode_rows = len(rows) - 1

                if actual_episode_rows <= episode_count * 2:
                    valid_season_tables.append(
                        {
                            "table": table,
                            "rows": rows,
                            "season_number": season_number,
                            "release_year": release_year,
                            "episode_count": episode_count,
                            "actual_episode_rows": actual_episode_rows,
                        }
                    )

        for table_info in valid_season_tables:
            seasons.append(
                SeasonInfo(
                    season_number=table_info["season_number"],
                    release_year=table_info["release_year"],
                )
            )

            table_episodes = self._parse_episodes_from_table_rows(
                table_info["rows"][1:], table_info["season_number"]
            )
            episodes.extend(table_episodes)

        return seasons, episodes

    def _parse_episodes_from_table_rows(
        self, rows, season_number: int
    ) -> List[EpisodeInfo]:
        """Parse episodes from table rows for a specific season."""
        episodes = []

        combined_text = ""
        for row in rows:
            row_text = row.get_text(strip=True)
            if row_text:
                combined_text += row_text + "\n"

        episode_parts = re.split(r"([Ээ]пизод\s+\d+)", combined_text)

        i = 1
        while i < len(episode_parts):
            if re.match(r"[Ээ]пизод\s+\d+", episode_parts[i]):
                episode_header = episode_parts[i]
                episode_content = (
                    episode_parts[i + 1] if i + 1 < len(episode_parts) else ""
                )

                episode_info = self._parse_single_episode(
                    episode_header + episode_content, season_number
                )
                if episode_info:
                    episodes.append(episode_info)
                i += 2
            else:
                i += 1

        return episodes

    def _parse_single_episode(
        self, text: str, season_number: int
    ) -> Optional[EpisodeInfo]:
        """Parse a single episode from text."""
        if not text:
            return None

        episode_match = re.search(r"[Ээ]пизод\s+(\d+)(.+)", text)

        if not episode_match:
            return None

        episode_number = int(episode_match.group(1))
        remaining_text = episode_match.group(2)

        episode = EpisodeInfo(
            season_number=season_number, episode_number=episode_number, title=""
        )

        episode_id_match = re.search(r"[Ээ]пизод\s*#(\d+(?:\.\d+)?)", remaining_text)
        if episode_id_match:
            episode.title = f"Эпизод #{episode_id_match.group(1)}"
        else:
            date_obj = None
            cleaned_text = remaining_text

            date_pattern = r"(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})"
            numeric_date_pattern = r"(\d{1,2}[.\-]\d{1,2}[.\-]\d{4})"
            year_only_pattern = r"(\d{4})$"

            dates_found = []

            russian_dates = list(re.finditer(date_pattern, remaining_text))
            dates_found.extend(russian_dates)

            numeric_dates = list(re.finditer(numeric_date_pattern, remaining_text))
            dates_found.extend(numeric_dates)

            dates_found.sort(key=lambda x: x.start(), reverse=True)

            for date_match in dates_found:
                date_str = date_match.group(1)
                validated_date = self._normalize_date(date_str)
                if validated_date and self._is_valid_date(validated_date):
                    date_obj = validated_date
                    cleaned_text = (
                        remaining_text[: date_match.start()]
                        + remaining_text[date_match.end() :]
                    )
                    cleaned_text = cleaned_text.strip()
                    break

            if date_obj is None:
                year_matches = list(re.finditer(year_only_pattern, remaining_text))
                if year_matches:
                    last_match = year_matches[-1]
                    year_str = last_match.group(1)
                    try:
                        year = int(year_str)
                        if 1900 <= year <= datetime.now().year + 5:
                            date_obj = date(year, 1, 1)
                            cleaned_text = remaining_text[: last_match.start()].strip()
                    except ValueError:
                        pass

            episode.release_date = date_obj

            title_info = self._extract_episode_titles(cleaned_text)
            episode.title = title_info["title"]
            episode.original_title = title_info["original_title"]

        if episode_id_match:
            date_obj = None

            date_pattern = r"(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})"
            numeric_date_pattern = r"(\d{1,2}[.\-]\d{1,2}[.\-]\d{4})"
            year_only_pattern = r"(\d{4})$"

            dates_found = []

            russian_dates = list(re.finditer(date_pattern, remaining_text))
            dates_found.extend(russian_dates)

            numeric_dates = list(re.finditer(numeric_date_pattern, remaining_text))
            dates_found.extend(numeric_dates)

            dates_found.sort(key=lambda x: x.start(), reverse=True)

            for date_match in dates_found:
                date_str = date_match.group(1)
                validated_date = self._normalize_date(date_str)
                if validated_date and self._is_valid_date(validated_date):
                    date_obj = validated_date
                    break

            if date_obj is None:
                year_matches = list(re.finditer(year_only_pattern, remaining_text))
                if year_matches:
                    last_match = year_matches[-1]
                    year_str = last_match.group(1)
                    try:
                        year = int(year_str)
                        if 1900 <= year <= datetime.now().year + 5:
                            date_obj = date(year, 1, 1)
                    except ValueError:
                        pass

            episode.release_date = date_obj

        if not episode.title:
            episode.title = f"Эпизод {episode_number}"

        return episode

    def _extract_episode_titles(self, text: str) -> Dict[str, Optional[str]]:
        """Extract both Russian and English titles from text."""
        result = {"title": "", "original_title": None}

        if not text:
            return result

        episode_pattern_match = re.search(r"[Ээ]пизод\s*#?(\d+(?:\.\d+)?)", text)
        if episode_pattern_match:
            result["title"] = f"Эпизод #{episode_pattern_match.group(1)}"
            result["original_title"] = None
            return result

        english_start = re.search(r"[A-Za-z]", text)
        if english_start:
            split_pos = english_start.start()
            russian_part = text[:split_pos].strip()
            english_part = text[split_pos:].strip()

            result["title"] = russian_part if russian_part else text.strip()
            result["original_title"] = english_part if english_part else None
        else:
            result["title"] = text.strip()
            result["original_title"] = None

        return result

    def _is_valid_date(self, date_obj: Optional[date]) -> bool:
        """Check if a date object is valid."""
        if not date_obj:
            return False
        try:
            if isinstance(date_obj, date):
                current_year = datetime.now().year
                if 1900 <= date_obj.year <= current_year + 5:
                    try:
                        date(date_obj.year, date_obj.month, date_obj.day)
                        return True
                    except ValueError:
                        return False
                return False
            return False
        except Exception:
            return False

    def _normalize_date(self, date_str: str) -> Optional[date]:
        """Normalize date string to date object."""
        if not date_str:
            return None

        months = {
            "января": 1,
            "февраля": 2,
            "марта": 3,
            "апреля": 4,
            "мая": 5,
            "июня": 6,
            "июля": 7,
            "августа": 8,
            "сентября": 9,
            "октября": 10,
            "ноября": 11,
            "декабря": 12,
        }

        russian_match = re.search(
            r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})",
            date_str,
        )
        if russian_match:
            day = int(russian_match.group(1))
            month_name = russian_match.group(2)
            year = int(russian_match.group(3))
            month = months[month_name]
            try:
                return date(year, month, day)
            except ValueError:
                return None

        numeric_match = re.search(r"(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})", date_str)
        if numeric_match:
            day = int(numeric_match.group(1))
            month = int(numeric_match.group(2))
            year = int(numeric_match.group(3))
            try:
                return date(year, month, day)
            except ValueError:
                return None

        numeric_match2 = re.search(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", date_str)
        if numeric_match2:
            year = int(numeric_match2.group(1))
            month = int(numeric_match2.group(2))
            day = int(numeric_match2.group(3))
            try:
                return date(year, month, day)
            except ValueError:
                return None

        return None

    def get_episodes_batch(self, movie_ids: List[int]) -> Dict[int, Dict[str, List]]:
        """Get episodes and seasons for multiple movie IDs."""
        results = {}

        for movie_id in movie_ids:
            print(f"Parsing episodes for movie ID: {movie_id}")
            data = self.get_episodes_and_seasons(movie_id)
            results[movie_id] = data

            # Be respectful to the server
            time.sleep(2)

        return results


def main():
    parser = KinopoiskEpisodesParser()
    movie_id = 893621  # Breaking Bad
    data = parser.get_episodes_and_seasons(movie_id)

    print(f"Found {len(data['seasons'])} seasons:")
    for season in data["seasons"]:
        print(
            f"  - Season {season.season_number}"
            + (f" ({season.release_year})" if season.release_year else "")
        )

    print(f"\nFound {len(data['episodes'])} episodes:")

    episodes_by_season = {}
    for episode in data["episodes"]:
        if episode.season_number not in episodes_by_season:
            episodes_by_season[episode.season_number] = []
        episodes_by_season[episode.season_number].append(episode)

    for season_num in sorted(episodes_by_season.keys()):
        episodes = episodes_by_season[season_num]
        print(f"  Season {season_num}:")
        for episode in episodes:
            date_str = (
                episode.release_date.strftime("%Y-%m-%d")
                if episode.release_date
                else "N/A"
            )
            title_display = episode.title
            if episode.original_title and episode.original_title != episode.title:
                title_display += f" ({episode.original_title})"
            print(f"    E{episode.episode_number}: {title_display} ({date_str})")


if __name__ == "__main__":
    main()
