# coding: utf-8
# Copyright (C) 2016 UKP lab
#
# Author: Daniil Sorokin (ukp.tu-darmstadt.de/ukp-home/)
#
import numpy as np
np.random.seed(1)

import json
import ast
import os

from relation_extraction.core import keras_models
from relation_extraction.graph import graph_utils
from core import embeddings

max_sent_len = 36


class RelParser:

    def __init__(self, relext_model_name, models_foldes="../trainedmodels/",
                 embeddings_location="glove/glove.6B.50d.txt", resource_folder="../resources/"):

        with open(models_foldes + relext_model_name + ".property2idx") as f:
            self._property2idx = ast.literal_eval(f.read())

        module_location = os.path.abspath(__file__)
        module_location = os.path.dirname(module_location)

        with open(os.path.join(module_location, "../model_params.json")) as f:
            model_params = json.load(f)

        self._embeddings, self._word2idx = embeddings.load(embeddings_location)
        print("Loaded embeddings:", self._embeddings.shape)
        self._idx2word = {v: k for k, v in self._word2idx.items()}

        self._model = keras_models.model_ContextWeighted(model_params,
                                                         np.zeros((len(self._word2idx), 50), dtype='float32'),
                                                         max_sent_len, len(self._property2idx))

        self._model.load_weights(models_foldes + relext_model_name + ".kerasmodel")

        with open(resource_folder + "properties-with-labels.txt") as infile:
            self._property2label = {l.split("\t")[0] : l.split("\t")[1].strip() for l in infile.readlines()}
        self._idx2property = {v: k for k, v in self._property2idx.items()}

        self._graphs_to_indices = keras_models.to_indices_with_real_entities
        if "CNN" in relext_model_name:
            self._graphs_to_indices = keras_models.to_indices_with_relative_positions

    def sem_parse(self, g, verbose=False):
        if verbose:
            print(" ".join(g['tokens']))

        data_as_indices = list(self._graphs_to_indices([g], self._word2idx, self._property2idx, max_sent_len, mode="test"))
        probabilities = self._model.predict(data_as_indices[:-1], verbose=0)
        if len(probabilities) == 0:
            return None
        probabilities = probabilities[0]
        classes = np.argmax(probabilities, axis=1)
        for i, e in enumerate(g['edgeSet']):
            if i < len(probabilities):
                e['kbID'] = self._idx2property[classes[i]]
                e["lexicalInput"] = self._property2label[e['kbID']] if e['kbID'] in self._property2label else embeddings.all_zeroes
                if verbose:
                    graph_utils.print_edge(e, g)
                    sorted_probabilities = sorted(enumerate(probabilities[i]), key=lambda x: x[1], reverse=True)
                    print("{} ({:.4}), {}".format(e['kbID'], np.max(probabilities[i]),
                                                  [(self._idx2property[p_id], p_prob) for p_id, p_prob in sorted_probabilities[1:4]]))
            else:
                e['kbID'] = "P0"
                e["lexicalInput"] = embeddings.all_zeroes
        return g
