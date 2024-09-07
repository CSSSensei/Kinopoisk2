import re


def get_id(s: str) -> int:
    match = re.search(r"id:\s+(\d+)", s)
    if match:
        id = match.group(1)
        return int(id)


def cut_back(s: str) -> str:
    last = 0
    lst = []
    while len(s) > 2048:
        for i in range(2048):
            if s[i] == '-' and s[i + 1] == ' ':
                last = i
        lst.append(s[:last])
        s = s[last:]
    return lst
