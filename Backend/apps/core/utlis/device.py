
def clean_serial_numbers(serial_numbers):

    return list(dict.fromkeys(
        sn.strip()
        for sn in serial_numbers
        if isinstance(sn, str) and sn.strip()
    ))