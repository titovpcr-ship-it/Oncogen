import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from gen_examples import ok, LANGS
class Quality(unittest.TestCase):
    def row(self, text): return dict(hy=text, **{l:'We read a book in the library.' for l in LANGS})
    def test_situation(self):
        self.assertTrue(ok('գիրք',self.row('Մենք այսօր գրադարանում միասին գիրք ենք կարդում։')))
    def test_templates(self):
        for text in ['Նա գիրք է։','Գիրք կարևոր է։','Նա այսօր գրադարանում նոր գիրք է կարդում։','Այս գիրքը ինձ համար շատ անհրաժեշտ է։']:
            with self.subTest(text=text): self.assertFalse(ok('գիրք',self.row(text)))
    def test_wrong_word_and_missing_translation(self):
        row=self.row('Մենք այսօր գրադարանում միասին գիրք ենք կարդում։')
        self.assertFalse(ok('բանան',row))
        row['pt']=''
        self.assertFalse(ok('գիրք',row))
if __name__=='__main__': unittest.main()
