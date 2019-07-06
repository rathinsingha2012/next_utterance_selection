# Copyright (c) 2017 AT&T Intellectual Property. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ==============================================================================

import numpy as np
import random
import sys
import math

def loadCharVocab(fname):
    charVocab={}
    with open(fname, 'rt') as f:
        for line in f:
            fields = line.strip().split('\t')
            char_id = int(fields[0])
            ch = fields[1]
            charVocab[ch] = char_id
    return charVocab

def loadVocab(fname):
    vocab={}
    idf={}
    with open(fname, 'rt') as f:
        for line in f:
            line = line.decode('utf-8').strip()
            fields = line.split('\t')
            term_id = int(fields[0])
            vocab[fields[1]] = term_id
            total_doc = int(fields[4])
            doc_freq = int(fields[3])
            idf[term_id] = math.log((0.5+total_doc)/(0.5+doc_freq))
    return vocab, idf

def toVec(tokens, vocab, maxlen):
    n = len(tokens)
    length = 0
    vec=[]
    for i in range(n):
        length += 1
        if tokens[i] in vocab:
            vec.append(vocab[tokens[i]])
        else:
            vec.append(vocab["UNKNOWN"])

    return length, np.array(vec)

def loadAnswers(fname, vocab, maxlen):
    answers={}
    with open(fname, 'rt') as f:
        for line in f:
            line = line.decode('utf-8').strip()
            fields = line.split('\t')
            if len(fields) != 2:
                print("WRONG LINE: {}".format(line))
                a_text = 'UNKNOWN'
            else:
                a_text = fields[1]
            tokens = a_text.split(' ')
            len1, vec = toVec(tokens[:maxlen], vocab, maxlen)
            answers[fields[0]] = (len1, vec, tokens[:maxlen])
    return answers

def loadDataset(fname, vocab, maxlen, answers):
    dataset=[]
    with open(fname, 'rt') as f:
        for line in f:
            line = line.decode('utf-8').strip()
            fields = line.split('\t')
            q_id = fields[0]
            question_text = fields[1]
            q_tokens = question_text.split(' ')
            q_len, q_vec = toVec(q_tokens[:maxlen], vocab, maxlen)
            if fields[3] != "NA":
                neg_ids = [id for id in fields[3].split('|')]
                for aid in neg_ids:
                    a_len, a_vec, a_tokens = answers[aid]
                    dataset.append((q_id, q_len, q_vec, aid, a_len, a_vec, 0.0, q_tokens[:maxlen], a_tokens))

            if fields[2] != "NA":
                pos_ids = [id for id in fields[2].split('|')]
                for aid in pos_ids:
                    a_len, a_vec, a_tokens = answers[aid]
                    dataset.append((q_id, q_len, q_vec, aid, a_len, a_vec, 1.0, q_tokens[:maxlen], a_tokens))
    return dataset

def word_count(q_vec, a_vec, q_len, a_len, idf):
    q_set = set([q_vec[i] for i in range(q_len) if q_vec[i] > 100])
    a_set = set([a_vec[i] for i in range(a_len) if a_vec[i] > 100])
    new_q_len = float(max(len(q_set), 1))
    count1 = 0.0
    count2 = 0.0
    for id1 in q_set:
        if id1 in a_set:
            count1 += 1.0
            if id1 in idf:
                count2 += idf[id1]
    return count1/new_q_len, count2/new_q_len

def common_words(q_vec, a_vec, q_len, a_len):
    q_set = set([q_vec[i] for i in range(q_len) if q_vec[i] > 100])
    a_set = set([a_vec[i] for i in range(a_len) if a_vec[i] > 100])
    return q_set.intersection(a_set)

def tfidf_feature(id_list, common_id_set, idf):
    word_freq={}
    for t in id_list:
        if t in common_id_set:
            if t in word_freq:
                word_freq[t] += 1
            else:
                word_freq[t] = 1
    tfidf_feature={}
    for t in common_id_set:
        if t in idf:
            tfidf_feature[t] = word_freq[t] * idf[t]
        else:
            tfidf_feature[t] = word_freq[t]
    return tfidf_feature

def word_feature(id_list, tfidf):
    len1 = len(id_list)
    features = np.zeros((len1, 2), dtype='float32')
    for idx, t in enumerate(id_list):
        if t in tfidf:
            features[idx, 0] = 1
            features[idx, 1] = tfidf[t]
    return features

def normalize_vec(vec, maxlen):
    if len(vec) == maxlen:
        return vec

    new_vec = np.zeros(maxlen, dtype='int32')
    for i in range(len(vec)):
        new_vec[i] = vec[i]
    return new_vec


def charVec(tokens, charVocab, maxlen, maxWordLength):
    n = len(tokens)
    if n > maxlen:
        n = maxlen

    chars =  np.zeros((maxlen, maxWordLength), dtype=np.int32)
    word_lengths = np.ones(maxlen, dtype=np.int32)
    for i in range(n):
        token = tokens[i][:maxWordLength]
        word_lengths[i] = len(token)
        row = chars[i]
        for idx, ch in enumerate(token):
            if ch in charVocab:
                row[idx] = charVocab[ch]

    return chars, word_lengths


def batch_iter(data, batch_size, num_epochs, target_loss_weights, idf, maxlen, charVocab, max_word_length, shuffle=True):
    """
    Generates a batch iterator for a dataset.
    """
    data_size = len(data)
    num_batches_per_epoch = int(len(data)/batch_size) + 1
    for epoch in range(num_epochs):
        # Shuffle the data at each epoch
        if shuffle:
            random.shuffle(data)
        for batch_num in range(num_batches_per_epoch):
            start_index = batch_num * batch_size
            end_index = min((batch_num + 1) * batch_size, data_size)
            x_question = []
            x_answer = []
            x_question_len = []
            x_answer_len = []
            targets = []
            target_weights=[]
            id_pairs =[]

            q_features=[]
            a_features=[]

            extra_feature =[]

            x_question_char=[]
            x_question_char_len=[]
            x_answer_char=[]
            x_answer_char_len=[]

            for rowIdx in range(start_index, end_index):
                q_id, q_len, q_vec, aid, a_len, a_vec, label, q_tokens, a_tokens = data[rowIdx]
                if label > 0:
                    target_weights.append(target_loss_weights[1])
                else:
                    target_weights.append(target_loss_weights[0])

                word_count_feature1, word_count_feature2 = word_count(q_vec, a_vec, q_len, a_len, idf)
                common_ids = common_words(q_vec, a_vec, q_len, a_len)
                tfidf = tfidf_feature(q_vec, common_ids, idf)
                new_q_vec = normalize_vec(q_vec, maxlen)
                new_a_vec = normalize_vec(a_vec, maxlen)

                q_word_feature = word_feature(new_q_vec, tfidf)
                a_word_feature = word_feature(new_a_vec, tfidf)
                x_question.append(new_q_vec)
                x_question_len.append(q_len)
                x_answer.append(new_a_vec)
                x_answer_len.append(a_len)
                targets.append(label)
                id_pairs.append((q_id, aid, int(label)))

                q_features.append(q_word_feature)
                a_features.append(a_word_feature)

                qCharVec, qCharLen = charVec(q_tokens, charVocab, maxlen, max_word_length)
                aCharVec, aCharLen = charVec(a_tokens, charVocab, maxlen, max_word_length)

                x_question_char.append(qCharVec)
                x_question_char_len.append(qCharLen)
                x_answer_char.append(aCharVec)
                x_answer_char_len.append(aCharLen)

                extra_feature.append(np.array([word_count_feature1, word_count_feature2], dtype="float32") )

            yield np.array(x_question), np.array(x_answer), np.array(x_question_len), np.array(x_answer_len), np.array(targets), np.array(target_weights), id_pairs, np.array(extra_feature), np.array(q_features), np.array(a_features), np.array(x_question_char), np.array(x_question_char_len), np.array(x_answer_char), np.array(x_answer_char_len)

