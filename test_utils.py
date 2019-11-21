from unittest import TestCase

from til import split_quoted


class TestUtils(TestCase):
    
    def test_split_quoted(self):
        string = 'abc, acd, a"aa"bb, a"a,a,a"cc'
        answer = ['abc', ' acd', ' a"aa"bb', ' a"a,a,a"cc']
        segments, closed = split_quoted(string, ',', '"')
        self.assertEqual(segments, answer)
        self.assertEqual(closed, True)
    
    def test_split_quoted_not_closed(self):
        string = 'abc, acd, a"aa"bb, a"a,a,a, cc'
        answer = ['abc', ' acd', ' a"aa"bb', ' a"a,a,a, cc']
        segments, closed = split_quoted(string, ',', '"')
        self.assertEqual(segments, answer)
        self.assertEqual(closed, False)
