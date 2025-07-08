class Movie:
    def __init__(self, id, ru_name, rating_kp, votes_kp, genres, rating_imdb, votes_imdb,
                 imdb, kphd, alternativeName, en_name, type, year, movieLength,
                 ratingMpaa, ageRating, countries, budget_value, fees_world,
                 top10, top250, productionCompanies, trailer, similarMovies,
                 sequelsAndPrequels, actors, director, description, shortDescription, formula, facts):
        self.id = id
        self.ru_name = ru_name
        self.rating_kp = rating_kp
        self.votes_kp = votes_kp
        self.genres = genres
        self.rating_imdb = rating_imdb
        self.votes_imdb = votes_imdb
        self.imdb = imdb
        self.kphd = kphd
        self.alternativeName = alternativeName
        self.en_name = en_name
        self.type = type
        self.year = year
        self.movieLength = movieLength
        self.ratingMpaa = ratingMpaa
        self.ageRating = ageRating
        self.countries = countries
        self.budget_value = budget_value
        self.fees_world = fees_world
        self.top10 = top10
        self.top250 = top250
        self.productionCompanies = productionCompanies
        self.trailer = trailer
        self.similarMovies = similarMovies
        self.sequelsAndPrequels = sequelsAndPrequels
        self.actors = actors
        self.director = director
        self.description = description
        self.shortDescription = shortDescription
        self.formula = formula
        self.facts = facts

    def __repr__(self):
        return f"<Movie id={self.id} name={self.ru_name or self.alternativeName or self.en_name}>"

    def __eq__(self, other):
        if not isinstance(other, Movie):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'ru_name': self.ru_name,
            'rating_kp': self.rating_kp,
            'votes_kp': self.votes_kp,
            'genres': self.genres,
            'rating_imdb': self.rating_imdb,
            'votes_imdb': self.votes_imdb,
            'imdb': self.imdb,
            'kphd': self.kphd,
            'alternativeName': self.alternativeName,
            'en_name': self.en_name,
            'type': self.type,
            'year': self.year,
            'movieLength': self.movieLength,
            'ratingMpaa': self.ratingMpaa,
            'ageRating': self.ageRating,
            'countries': self.countries,
            'budget_value': self.budget_value,
            'fees_world': self.fees_world,
            'top10': self.top10,
            'top250': self.top250,
            'productionCompanies': self.productionCompanies,
            'trailer': self.trailer,
            'similarMovies': self.similarMovies,
            'sequelsAndPrequels': self.sequelsAndPrequels,
            'actors': self.actors,
            'director': self.director,
            'description': self.description,
            'shortDescription': self.shortDescription,
            'formula': self.formula,
            'facts': self.facts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Movie':
        return cls(**data)
