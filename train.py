#!/usr/bin/env python
# coding:utf-8


import numpy as np
import time
import datetime
import os
import tensorflow as tf
from tensorflow.python.layers.core import Dense
from utils import Utils
from seq2seq_model import Seq2SeqModel


### hyper parameters
lr = 1e-3
epochs = 1000
batch_size = 32
rnn_size = 50
num_layers = 2
encoding_embedding_size = 15
decoding_embedding_size = 15
num_checkpoints = 10
evaluate_every = 100
checkpoint_every = 100

### data preprocessing
utils = Utils()
x, y = utils.generate_char_x_y(data_size=10000, seed=314)
data = x + y
id2word_x, word2id_x = utils.extract_character_vocab(x)
id2word_y, word2id_y = utils.extract_character_vocab(y)
x_vocab_size = len(id2word_x)
y_vocab_size = len(id2word_y)

# 将每一行转换成字符id的list
x_ids = [[word2id_x.get(word, word2id_x['<UNK>'])
    for word in sentence] for sentence in x]
y_ids = [[word2id_y.get(word, word2id_y['<UNK>'])
    for word in sentence] + [word2id_y['<EOS>']] for sentence in y]
print(len(x_ids))
print(len(y_ids))
x_train = x_ids[:]
y_train = y_ids[:]
data_size_train = len(x_train)



### training
# ===============================================

with tf.Graph().as_default():
    session_conf = tf.ConfigProto(allow_soft_placement=True, log_device_placement=False)
    sess = tf.Session(config=session_conf)

    with sess.as_default():
        seq2seq_model = Seq2SeqModel(
            x_vocab_size=x_vocab_size,
            y_vocab_size=y_vocab_size,
            encoder_embedding_size=encoding_embedding_size,
            decoder_embedding_size=decoding_embedding_size,
            rnn_size=rnn_size,
            num_layers=num_layers,
            word2id_x=word2id_x,
            word2id_y=word2id_y,
            seed=314
            )

        # define training procedure
        global_step = tf.Variable(0, trainable=False, name='global_step')
        optimizer = tf.train.AdamOptimizer(learning_rate=lr)
        grads_and_vars = optimizer.compute_gradients(seq2seq_model.loss)
        train_op = optimizer.apply_gradients(grads_and_vars, global_step=global_step)

        # output directory for models and summaries
        timestamp = str(int(time.time()))
        out_dir = os.path.abspath(os.path.join(os.curdir, 'log', timestamp))
        print('Writing log to {}\n'.format(out_dir))

        # summary all the trainable variables
        for var in tf.trainable_variables():
            tf.summary.histogram(name=var.name, values=var)

        # summaries for loss and accuracy
        loss_summary = tf.summary.scalar('loss', seq2seq_model.loss)
        # acc_summary = tf.summary.scalar('accuracy', seq2seq_model.accuracy)

        # train summaries
        train_summary_op = tf.summary.merge_all()
        train_summary_dir = os.path.join(out_dir, 'summaries', 'train')
        train_summary_writer = tf.summary.FileWriter(train_summary_dir, tf.get_default_graph())

        # dev summaries
        dev_summary_op = tf.summary.merge_all()
        dev_summary_dir = os.path.join(out_dir, 'summaries', 'dev')
        dev_summary_writer = tf.summary.FileWriter(dev_summary_dir, tf.get_default_graph())

        # checkpointing, tensorflow assumes this directory already existed, so we need to create it
        checkpoint_dir = os.path.join(out_dir, 'checkpoints')
        checkpoint_prefix = os.path.join(checkpoint_dir, 'model')
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)
        saver = tf.train.Saver(tf.global_variables(), max_to_keep=num_checkpoints)

        # initialize all variables
        sess.run(tf.global_variables_initializer())

        # function for a single training step
        def train_step(x_batch, y_batch, x_length, y_length, writer=None):
            '''
            A single training step.
            '''
            feed_dict = {
                seq2seq_model.input_x: x_batch,
                seq2seq_model.input_y: y_batch,
                seq2seq_model.x_sequence_length: x_length,
                seq2seq_model.y_sequence_length: y_length
            }
            _, step, summaries, loss = sess.run(
                [train_op, global_step, train_summary_op, seq2seq_model.loss],
                feed_dict)
            timestr = datetime.datetime.now().isoformat()
            num_batches_per_epoch = int((data_size_train-1)/batch_size)+1
            epoch = int((step-1)/num_batches_per_epoch)+1
            print('{}: => epoch {} | step {} | loss {:g}'.format(timestr, epoch, step, loss))
            if writer:
                writer.add_summary(summaries, step)

        # def dev_step(x_batch, y_batch, writer=None):
        #     '''
        #     Evalute the model on dev set.
        #     '''
        #     feed_dict = {
        #         cnn.input_x: x_batch,
        #         cnn.input_y: y_batch,
        #         cnn.dropout_keep_prob: 1.0
        #     }
        #     step, summaries, loss, accuracy = sess.run(
        #         [global_step, dev_summary_op, cnn.loss, cnn.accuracy],
        #         feed_dict)
        #     timestr = datetime.datetime.now().isoformat()
        #     num_batches_per_epoch = int((data_size_train-1)/FLAGS.batch_size)+1
        #     epoch = int(step/num_batches_per_epoch)+1
        #     print('{}: => epoch {} | step {} | loss {:g} | acc {:g}'.format(timestr, epoch, step, loss, accuracy))
        #     if writer:
        #         writer.add_summary(summaries, step)

        ### training loop
        # generate batches
        # train loop, for each batch
        for batch_i, (x_batch, y_batch, x_lengths, y_lengths) in enumerate(utils.batch_iter(
             epochs, x_train, y_train, batch_size, word2id_x['<PAD>'], word2id_y['<PAD>'])):

            train_step(x_batch, y_batch, x_lengths, y_lengths, writer=train_summary_writer)
            current_step = tf.train.global_step(sess, global_step)
            if current_step % evaluate_every == 0:
                print('\nEvaluation on dev set:')
                # dev_step(x_dev, y_dev, writer=dev_summary_writer)
                print('')
            if current_step % checkpoint_every == 0:
                path = saver.save(sess=sess, save_path=checkpoint_prefix, global_step=global_step)
                print('\nSaved model checkpoint to {}\n'.format(path))