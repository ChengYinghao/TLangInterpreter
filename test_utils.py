from unittest import TestCase

from til import quoted_split


class TestUtils(TestCase):
    
    def test_quoted_split(self):
        string = 'abc, acd, a"aa"bb, a"a,a,a"cc'
        answer = ['abc', ' acd', ' a"aa"bb', ' a"a,a,a"cc']
        segments, closed = quoted_split(string, ',', '"')
        self.assertEqual(segments, answer)
        self.assertEqual(closed, True)
    
    def test_quoted_split_not_closed(self):
        string = 'abc, acd, a"aa"bb, a"a,a,a, cc'
        answer = ['abc', ' acd', ' a"aa"bb', ' a"a,a,a, cc']
        segments, closed = quoted_split(string, ',', '"')
        self.assertEqual(segments, answer)
        self.assertEqual(closed, False)
