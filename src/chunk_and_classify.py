import pandas as pd
import numpy as np
import regex as re
import nltk
from nltk.corpus import stopwords
from nltk.corpus import conll2000
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.linear_model import SGDClassifier
from sklearn import metrics
from utils import path_compiler


grammar = r"""
  NP: {<JJ><NN|NNS><NN|NNS|VBG>}   # chunk adjective and2 consecutive noun/nouns or 
      {<NN|NNS><NN|NNS|VBG>}
      {<JJ><NN|NNS>}
      {<NN|NNS>}
      {<NNP><NNP><NN|NNS|VBG>}
      {<NNP><NN|NNS|VBG>}
      {<NNP>}                # chunk of 1 proper noun
"""


class ConsecutiveNPChunkTagger(nltk.TaggerI):
    def __init__(self, train_sents, path_to_megam):
        train_set = []
        for tagged_sent in train_sents:
            untagged_sent = nltk.tag.untag(tagged_sent)
            history = []
            for i, (word, tag) in enumerate(tagged_sent):
                featureset = self.npchunk_features(untagged_sent, i, history)
                train_set.append((featureset, tag))
                history.append(tag)
        nltk.config_megam(path_to_megam)
        self.classifier = nltk.MaxentClassifier.train(
            train_set, algorithm="megam", trace=0
        )

    def tag(self, sentence):
        history = []
        for i, word in enumerate(sentence):
            featureset = self.npchunk_features(sentence, i, history)
            tag = self.classifier.classify(featureset)
            history.append(tag)
        return zip(sentence, history)

    def npchunk_features(self, sentence, i, history):
        word, pos = sentence[i]
        if i == 0:
            prevword, prevpos = "<START>", "<START>"
        else:
            prevword, prevpos = sentence[i - 1]
        if i == len(sentence) - 1:
            nextword, nextpos = "<END>", "<END>"
        else:
            nextword, nextpos = sentence[i + 1]
        return {
            "pos": pos,
            "word": word,
            "prevpos": prevpos,
            "nextpos": nextpos,
            "prevpos+pos": "%s+%s" % (prevpos, pos),
            "pos+nextpos": "%s+%s" % (pos, nextpos),
            "tags-since-dt": self.tags_since_dt(sentence, i),
        }

    def tags_since_dt(sentence, i):
        tags = set()
        for word, pos in sentence[:i]:
            if pos == "DT":
                tags = set()
            else:
                tags.add(pos)
        return "+".join(sorted(tags))


class ConsecutiveNPChunker(nltk.ChunkParserI):
    def __init__(self, train_sents):
        tagged_sents = [
            [((w, t), c) for (w, t, c) in nltk.chunk.tree2conlltags(sent)]
            for sent in train_sents
        ]
        self.tagger = ConsecutiveNPChunkTagger(tagged_sents)

    def parse(self, sentence):
        tagged_sents = self.tagger.tag(sentence)
        conlltags = [(w, t, c) for ((w, t), c) in tagged_sents]
        return nltk.chunk.conlltags2tree(conlltags)


class Chunker:
    def __init__(self):
        self.train_sents = conll2000.chunked_sents("train.txt", chunk_types=["NP"])
        self.consecutive_np_chunker = ConsecutiveNPChunker(self.train_sents)
        self.regex_chunker = nltk.RegexpParser(grammar)
        self.contractions = path_compiler(
            "src", "resources", "contractions.json", "json"
        )

    def clean_text(self, text):

        # Expand contractions
        if True:
            text = text.split()
            new_text = []
            for word in text:
                if word in self.contractions:
                    new_text.append(self.contractions[word])
                else:
                    new_text.append(word)
            text = " ".join(new_text)

        # Format words and remove unwanted characters
        # text = re.sub(r'https?:\/\/.*[\r\n]*', '', text, flags=re.MULTILINE)
        # text = re.sub(r'\<a href', ' ', text)
        text = re.sub(r"\ufeff", "", text)
        # text = re.sub(r'&amp;', '', text)
        # text = re.sub(r'[_"\-;%()|+&=*%,!?:#$@\[\]/]', ' ', text)
        # text = re.sub(r'<br />', ' ', text)
        # text = re.sub(r'\'', ' ', text)

        # Tokenize each word
        # text =  nltk.WordPunctTokenizer().tokenize(text)
        sentences = nltk.sent_tokenize(text)
        sentences = [nltk.word_tokenize(sent) for sent in sentences]
        sentences = [nltk.pos_tag(sent) for sent in sentences]

        return sentences

    def extract_np_chunks(self, tagged_trees):
        np_chunks = []
        for s in tagged_trees:
            if isinstance(s, nltk.tree.Tree):
                for chunk in s:
                    if isinstance(chunk, tuple):
                        pass
                    else:
                        if chunk.label() == "NP":
                            chunk_text = ""
                            for t in chunk:
                                chunk_text += t[0] if chunk_text == "" else f" {t[0]}"
                            np_chunks.append(chunk_text)
        return np_chunks

    def get_chunks_from_chunkers(self, text):
        processed_text = self.clean_text(text)
        text1 = [
            self.consecutive_np_chunker.parse(sentence) for sentence in processed_text
        ]
        text2 = [self.regex_chunker.parse(sentence) for sentence in processed_text]
        text = text1 + text2
        np_chunks = self.extract_np_chunks(text)
        np_chunks = list(dict.fromkeys(np_chunks))
        return np_chunks


class TextClassifier:
    def __init__(self):
        self.chunk_train_df = pd.read_csv(
            path_compiler("src", "resources", "skills_matched.csv", "csv")
        )
        self.bow_converter = CountVectorizer()
        self.tfidf_transformer = TfidfTransformer()
        self.classifier = self.train_classifier_pipeline_sgd()

    def train_classifier_multinominal(self):
        x = self.bow_converter.fit_transform(self.chunk_train_df["Chunk"])
        X_train_tfidf = self.tfidf_transformer.fit_transform(x)
        clf = MultinomialNB().fit(X_train_tfidf, self.chunk_train_df["Result"])
        return clf

    def train_classifier_pipeline_multinominal(self):
        text_clf = Pipeline(
            [
                ("vect", CountVectorizer()),
                ("tfidf", TfidfTransformer()),
                ("clf", MultinomialNB()),
            ]
        )
        text_clf.fit(self.chunk_train_df["Chunk"], self.chunk_train_df["Result"])
        return text_clf

    def train_classifier_pipeline_sgd(self):
        text_clf = Pipeline(
            [
                ("vect", CountVectorizer()),
                ("tfidf", TfidfTransformer()),
                (
                    "clf",
                    SGDClassifier(
                        loss="hinge",
                        penalty="l2",
                        alpha=1e-3,
                        random_state=42,
                        max_iter=5,
                        tol=None,
                    ),
                ),
            ]
        )
        text_clf.fit(self.chunk_train_df["Chunk"], self.chunk_train_df["Result"])
        return text_clf

    def get_metrics(self, predicted, target):
        self.mean_diff = np.mean(predicted == target)
        self.classifications_report = metrics.classification_report(
            target, predicted
        )  # target_names=
        self.confusion_matrix = metrics.confusion_matrix(target, predicted)

    def predict(self, chunks):
        df = pd.DataFrame()
        df.loc["Chunk"] = chunks
        skill_or_not = []
        for chunk in chunks:
            skill_or_not.append(self.classifier.predict(chunk))
        df["Result"] = skill_or_not
        return list(df.loc[df["Result"] == 1]["Chunk"])
