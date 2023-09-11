from typing import Any, Dict, List
from remove_HTML import remove_html_tags


def get_row(item: Dict) -> Dict[str, Any]:
    countries = item.get('countries', {})
    country_name = countries[0]['name'] if isinstance(countries, list) and len(countries) > 0 else None
    facts = item.get('facts')
    facts_string = None
    if facts is not None:
        facts_string = ''
        for j in facts:
            string = remove_html_tags(j['value'])
            flag = j.get('spoiler', False)
            if flag:
                facts_string += '- Острожно! Спойлер! <spoiler>'
                facts_string += string + '</spoiler> \n'
            else:
                facts_string += "- " + string + '\n'

    comp = item.get('productionCompanies', [])
    companies = ', '.join([i['name'] for i in comp]) if len(comp) > 0 else None
    if item.get('similarMovies') is not None:
        similar = '\n'.join(
            [str(i['name']) + ' (id: ' + str(i.get('id', 'no info')) + ')' for i in item.get('similarMovies') if
             i.get('name') is not None]) if len(
            item.get('similarMovies')) > 0 else None
    else:
        similar = None
    if item.get('similarMovies') is not None:
        sequels_prequels = '\n'.join(
            [str(i['type']) + ': ' + str(i['name']) + ' (id: ' + str(i.get('id', 'no info')) + ')' for i in
             item.get('sequelsAndPrequels') if i.get('name') is not None]) \
            if len(item.get('sequelsAndPrequels')) > 0 else None
    else:
        sequels_prequels = None
    budget = item.get('budget', {}).get('value')
    if budget is not None:
        budget = str(item.get('budget', {}).get('value')) + ' ' + str(item.get('budget', {}).get('currency'))
    fees = item.get('fees', {}).get('world', {}).get('value')
    if fees is not None:
        fees = str(item.get('fees', {}).get('world', {}).get('value')) + ' ' + str(
            item.get('fees', {}).get('world', {}).get('currency'))

    if item is not None and item.get('videos') is not None and len(item.get('videos').get('trailers', {})) > 0:
        trailer = item.get('videos').get('trailers', {})[0].get('url')
    else:
        trailer = None

    persons: List[Any | Dict] = item.get('persons', [])
    actors = []
    director = []
    for j in persons:
        if len(j.get('profession', [])) != 0:
            if (j['profession'] == 'актеры') and (j['name'] is not None):
                actors.append(j['name'])
            elif j['profession'] == 'режиссеры' and (j['name'] is not None):
                director.append(j['name'])

    row: Dict[str, Any] = {
        'ru_name': item.get('name'),
        'rating_kp': -1 if item.get('rating', {}).get('kp') is None else float(
            item.get('rating', {}).get('kp')),
        'votes_kp': -1 if item.get('votes', {}).get('kp') is None else int(item.get('votes', {}).get('kp')),
        'genres': ', '.join([r['name'] for r in item.get('genres')]),
        'rating_imdb': -1 if item.get('rating', {}).get('imdb') is None else float(
            item.get('rating', {}).get('imdb')),
        'votes_imdb': -1 if item.get('votes', {}).get('imdb') is None else int(
            item.get('votes', {}).get('imdb')),
        'id': int(item.get('id')),
        'imdb': item.get('externalId', {}).get('imdb'),
        'kphd': item.get('externalId', {}).get('kpHD'),
        'alternativeName': item.get('alternativeName'),
        'en_name': item.get('enName'),
        'type': item.get('type'),
        'year': -1 if item.get('year') is None else int(item.get('year')),
        'movieLength': -1 if item.get('movieLength') is None else int(item.get('movieLength')),
        'ratingMpaa': item.get('ratingMpaa'),
        'ageRating': -1 if item.get('ageRating') is None else int(item.get('ageRating')),
        'countries': country_name,
        'budget_value': budget,
        'fees_world': fees,
        'top10': -1 if item.get('top10') is None else int(item.get('top10')),
        'top250': -1 if item.get('top250') is None else int(item.get('top250')),
        'facts': facts_string,
        'productionCompanies': companies,
        'trailer': trailer,
        'similarMovies': similar,
        'sequelsAndPrequels': sequels_prequels,
        'actors': ', '.join(actors),
        'director': ', '.join(director),
        'description': item.get('description'),
        'shortDescription': item.get('shortDescription'),
        'formula': -1
    }
    return row
