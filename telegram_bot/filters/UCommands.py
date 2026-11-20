import re
from typing import List


def get_link(movie_id: int):
    return f'http://www.kinopoisk.ru/images/film_big/{movie_id}.jpg'


def get_id(s: str) -> int:
    match = re.search(r"id:\s+(\d+)", s)
    if match:
        id = match.group(1)
        return int(id)


def cut_string(s: str, n: int = 90, symbol: str = ','):
    if len(s) <= n:
        return s

    last_comma_index = s.rfind(symbol, 0, n)

    if last_comma_index == -1:
        return s[:n]
    return s[:last_comma_index]


def cut_back(s: str) -> list:
    lst = []
    while len(s) > 2048:
        last = s.rfind('- ', 0, 2048)
        if last == -1:
            break
        lst.append(s[:last])
        s = s[last + 2:]
    lst.append(s)
    return lst


def split_text(text, n) -> List[str]:
    result = []
    lines = text.split('\n')
    current_chunk = ''
    current_length = 0

    for line in lines:
        if len(current_chunk) + len(line) + 1 <= n:  # Check if adding the line and '\n' fits in the chunk
            if current_chunk:  # Add '\n' if it's not the first line in the chunk
                current_chunk += '\n'
            current_chunk += line
            current_length += len(line) + 1
        else:
            result.append(current_chunk)
            current_chunk = line
            current_length = len(line)

    if current_chunk:
        result.append(current_chunk)

    return result


if __name__ == '__main__':
    print(cut_back('- fadsfasdfasd'))
