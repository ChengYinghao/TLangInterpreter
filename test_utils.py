from unittest import TestCase

from tli import quoted_split, quoted_split_first


class TestUtils(TestCase):
    
    def test_quoted_split_first(self):
        string = 'abcbc"ac,cd,",ab,acb,"b"'
        answer = 'abcbc"ac,cd,"', 'ab,acb,"b"'
        segments = quoted_split_first(string, ',', '"')
        self.assertEqual(segments, answer)
    
    def test_quoted_split_first_not_found(self):
        string = 'abcbc"ac,cdb"'
        answer = None, string
        segments = quoted_split_first(string, ',', '"')
        self.assertEqual(segments, answer)
    
    def test_quoted_split_first_not_closed(self):
        string = 'abcbc"ac,cdb'
        answer = None, string
        segments = quoted_split_first(string, ',', '"')
        self.assertEqual(segments, answer)
    
    def test_quoted_split(self):
        string = 'abc,acd,a"aa"bb,a"a,a,a"cc'
        answer = ['abc', 'acd', 'a"aa"bb', 'a"a,a,a"cc']
        segments, closed = quoted_split(string, ',', '"')
        self.assertEqual(segments, answer)
        self.assertEqual(closed, True)
    
    def test_quoted_split_not_closed(self):
        string = 'abc,acd,a"aa"bb,a"a,a,a,cc'
        answer = ['abc', 'acd', 'a"aa"bb', 'a"a,a,a,cc']
        segments, closed = quoted_split(string, ',', '"')
        self.assertEqual(segments, answer)
        self.assertEqual(closed, False)
