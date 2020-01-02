from __future__ import absolute_import, division, print_function, unicode_literals

import numpy as np
import tensorflow as tf
import os, pickle, random, nltk, math, sqlite3, time
import matplotlib.pyplot as plt

def get_num_words_per_sample(sample_texts):
    """Returns the median number of words per sample given corpus.

    # Arguments
        sample_texts: list, sample texts.

    # Returns
        int, median number of words per sample.
    """
    num_words = [len(s.split()) for s in sample_texts]
    return np.median(num_words)

def plot_sample_length_distribution(sample_texts):
    """Plots the sample length distribution.

    # Arguments
        samples_texts: list, sample texts.
    """
    plt.hist([len(s) for s in sample_texts], 50)
    plt.xlabel('Length of a sample')
    plt.ylabel('Number of samples')
    plt.title('Sample length distribution')
    plt.show()

def loaddata(seed=123):
    category_list = ['AD','B','CS','LC','LG','LL','LS','M','R','RL','RM','SD','SS','T','TW']
    news= []
    labels = []
    newstext = []
    for category in category_list:
        for entry in os.scandir(f'../../trainer/TheStreet/{category}/'):
            if not entry.name.startswith('.') and entry.is_file() and entry.name.find('labeled') != -1:
                with open(f'../../trainer/{category}/{entry.name}') as f:
                    data = f.read()
                    news.append([data, category, entry.name])
                print(entry.name)
    random.seed(seed)
    random.shuffle(news)
    for entry in news:
        newstext.append(entry[0])
        labels.append(entry[1])
    train_index = math.ceil(len(newstext) / 2)
    train_texts=newstext[0:train_index]
    test_texts=newstext[train_index:]
    train_labels=labels[0:train_index]
    test_labels=labels[train_index:]
    return ((train_texts, np.array(train_labels)),
            (test_texts, np.array(test_labels)))

def _get_last_layer_units_and_activation(num_classes):
    """Gets the # units and activation function for the last network layer.

    # Arguments
        num_classes: int, number of classes.

    # Returns
        units, activation values.
    """
    if num_classes == 2:
        activation = 'sigmoid'
        units = 1
    else:
        activation = 'softmax'
        units = num_classes
    return units, activation

from tensorflow.python.keras import models
from tensorflow.python.keras.layers import Dense
from tensorflow.python.keras.layers import Dropout

def mlp_model(layers, units, dropout_rate, input_shape, num_classes):
    """Creates an instance of a multi-layer perceptron model.

    # Arguments
        layers: int, number of `Dense` layers in the model.
        units: int, output dimension of the layers.
        dropout_rate: float, percentage of input to drop at Dropout layers.
        input_shape: tuple, shape of input to the model.
        num_classes: int, number of output classes.

    # Returns
        An MLP model instance.
    """
    op_units, op_activation = _get_last_layer_units_and_activation(num_classes)
    model = models.Sequential()
    model.add(Dropout(rate=dropout_rate, input_shape=input_shape))

    for _ in range(layers-1):
        model.add(Dense(units=units, activation='relu'))
        model.add(Dropout(rate=dropout_rate))

    model.add(Dense(units=op_units, activation=op_activation))
    return model