from abc import ABC, abstractmethod
from typing import List, Dict, Union

from config_data.models import Movie


class AbstractMovieDB(ABC):
    @abstractmethod
    def search_by_name(self, name: str) -> List[Movie]:
        pass

    @abstractmethod
    def search_en_name(self, name: str) -> List[Movie]:
        pass

    @abstractmethod
    def random_film(self) -> Union[Movie, None]:
        pass

    @abstractmethod
    def get_facts(self, id: int) -> str:
        pass

    @abstractmethod
    def search_by_id(self, id: int) -> Union[Movie, None]:
        pass

    @abstractmethod
    def get_info(self, movie: Movie) -> List[str]:
        pass

    @abstractmethod
    def filter_database(self, filters: Dict[str, Union[str, bool]]) -> List[Movie]:
        pass
