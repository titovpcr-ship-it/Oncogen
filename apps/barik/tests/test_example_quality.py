import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from gen_examples import ok, LANGS
from build_examples import contains_word_stem
class Quality(unittest.TestCase):
    def row(self, text): return dict(hy=text, **{l:'We read a book in the library.' for l in LANGS})
    def test_situation(self):
        self.assertTrue(ok('գիրք',self.row('Մենք այսօր գրադարանում միասին գիրք ենք կարդում։')))
    def test_attested_noun_inflections(self):
        self.assertTrue(contains_word_stem('արագ սնունդ', 'Բժիշկը խոսեց արագ սննդի ազդեցության մասին։'))
        self.assertTrue(contains_word_stem('բացատրական դերանուն', 'Դասարանում քննարկեցինք բացատրական դերանվան գործածությունը։'))
        self.assertTrue(contains_word_stem('Հոգեգալուստ', 'Հոգեգալստյան տոնին երգչախումբը եկեղեցում շարական երգեց։'))
        self.assertTrue(contains_word_stem('ավազակախումբ', 'Արխիվում գտանք ավազակախմբի մասին հին գրառումը։'))
        self.assertTrue(contains_word_stem('գետնատուն', 'Գետնատան մուտքը ծածկված էր կանաչ ճյուղերով։'))
        self.assertTrue(contains_word_stem('աբբահայր', 'Մատենադարանում գտանք աբբահոր ձեռագրի լուսապատճենը։'))
        self.assertTrue(contains_word_stem('Վրացագիտություն', 'Գրադարանում բացվեց վրացագիտության նոր բաժինը։'))
        self.assertTrue(contains_word_stem('գորշ ածուխ', 'Լաբորատորիայում ուսումնասիրեցինք գորշ ածխի նոր նմուշը։'))
        self.assertTrue(contains_word_stem('ուղղանկյուն եռանկյուն', 'Աշակերտը չափեց ուղղանկյուն եռանկյան երկու կողմերը։'))
        self.assertTrue(contains_word_stem('քուրձ', 'Թանգարանում ուսումնասիրեցինք քրձից պատրաստված հին հագուստը։'))
        self.assertTrue(contains_word_stem('արեւելաեվրոպական', 'Նկարիչը ուսումնասիրեց արևելաեվրոպական հին զարդանախշերը։'))
        self.assertFalse(contains_word_stem('արագ սնունդ', 'Մարզիկը արագ վազեց դեպի մարզադաշտը։'))
    def test_templates(self):
        for text in ['Նա գիրք է։','Գիրք կարևոր է։','Նա այսօր գրադարանում նոր գիրք է կարդում։','Այս գիրքը ինձ համար շատ անհրաժեշտ է։']:
            with self.subTest(text=text): self.assertFalse(ok('գիրք',self.row(text)))
    def test_wrong_word_and_missing_translation(self):
        row=self.row('Մենք այսօր գրադարանում միասին գիրք ենք կարդում։')
        self.assertFalse(ok('բանան',row))
        row['pt']=''
        self.assertFalse(ok('գիրք',row))
if __name__=='__main__': unittest.main()
