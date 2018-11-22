import click


@click.command()
def main(limit):
    # sha1 range
    # 160 bits (20 byte) length
    bound_max_minus = 2**159
    bound_max = 2**160 - 1
    step = 2**16

    def to_hex(number):
        return '{:040x}'.format(number)

    for start, end in zip(
            range(0, bound_max_minus, step), range(step, bound_max, step)):
        hex_start = to_hex(start)
        hex_end = to_hex(end)
        print('["%s", "%s"]' % (hex_start, hex_end))


if __name__ == '__main__':
    main()
