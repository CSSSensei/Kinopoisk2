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
