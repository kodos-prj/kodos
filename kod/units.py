# Capacity unit conversion

import re

def convert2byte(value_unit: str) -> tuple[int,str]:
    _,value,unit = re.split("([0-9]+)",value_unit)
    value = int(value)
    
    if unit=="%":
        return value,unit
    if not unit:
        return value,'B'
    
    match unit:
        case "B":
            value_b = value
        case "KiB": 
            value_b = (value * 2**10)
        case "MiB": 
            value_b = (value * 2**20)
        case "GiB": 
            value_b = (value * 2**30)
        case "TiB": 
            value_b = (value * 2**40)
        case "KB": 
            value_b = value * (10**3)
        case "MB": 
            value_b = value * (10**6)
        case "GB": 
            value_b = value * (10**9)
        case "TB": 
            value_b = value * (10**12)
        case _: 
            print(f"Wrong unit {unit}")
            raise Exception(f"Wrong units {unit}")
    return value_b,'B'


def add_value_unit(value1, value2):
    val1,unit1 = convert2byte(value1)
    val2,unit2 = convert2byte(value2)
    if unit1 == unit2 and unit1 == 'B':
        return val1 + val2, 'B'
    return val2,unit2


if __name__ == "__main__":    
    print(f"{convert2byte('1KiB')=}")
    print(f"{convert2byte('1MiB')=}")
    print(f"{convert2byte('1GiB')=}")
    print(f"{convert2byte('1KB')=}")
    print(f"{convert2byte('1MB')=}")
    print(f"{convert2byte('1GB')=}")
    print(f"{convert2byte('80%')=}")
    # print(f"{convert2byte('80kib')=}")

    print(f"{add_value_unit('1KiB','1KB')=}")
    print(f"{add_value_unit('2KiB','3MiB')=}")
    print(f"{add_value_unit('1MiB','40%')=}")

