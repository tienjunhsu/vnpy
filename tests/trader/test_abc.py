from abc import ABC


class Test(ABC):

    def __init__(self,
                 aa: str,
                 bb: str = None):
        self.aa = aa
        self.bb = bb

    def print(self):
        print(self.aa)
        print(self.bb)


if __name__ == '__main__':
    aa = Test('abc')
    aa.print()
    print('aaaaaaaaaaaaaaaaaaa')
    bb = Test('abc', '1234')
    bb.print()
