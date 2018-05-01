import os
import tensorflow as tf
import tensorlayer as tl
from tensorlayer.layers import \
    InputLayer, Conv1d, MaxPool1d, \
    RNNLayer, DropoutLayer, DenseLayer, \
    LambdaLayer, ReshapeLayer, ConcatLayer, \
    Conv2d, MaxPool2d, FlattenLayer, \
    DeConv2d, BatchNormLayer, EmbeddingInputlayer, \
    Seq2Seq, retrieve_seq_length_op2

import config

class Model4Text():

    def __init__(
            self,
            model_name,
            start_learning_rate,
            decay_rate,
            decay_steps,
            vocab_size=config.vocab_size
    ):
        self.model_name = model_name
        self.start_learning_rate = start_learning_rate
        self.decay_rate = decay_rate
        self.decay_steps = decay_steps
        self.vocab_size = vocab_size

        self.__create_placeholders__()
        self.__create_model__()
        self.__create_loss__()
        self.__create_training_op__()


    def __create_placeholders__(self):
        self.encode_seqs = tf.placeholder(dtype=tf.int64, shape=[config.batch_size, None], name="encode_seqs")
        self.decode_seqs = tf.placeholder(dtype=tf.int64, shape=[config.batch_size, None], name="decode_seqs")
        self.target_seqs = tf.placeholder(dtype=tf.int64, shape=[config.batch_size, None], name="target_seqs")
        self.target_mask = tf.placeholder(dtype=tf.int64, shape=[config.batch_size, None], name="target_mask")


    def __create_model__(self):
        self.train_net, self.train_seq2seq = self.__get_network__(self.model_name, self.encode_seqs, self.decode_seqs, reuse=False)
        self.test_net, self.test_seq2seq = self.__get_network__(self.model_name, self.encode_seqs, self.decode_seqs, reuse=True)

        self.train_text_state = self.train_seq2seq.final_state_encode
        self.test_text_state = self.test_seq2seq.final_state_encode


    def __get_network__(self, model_name, encode_seqs, decode_seqs, reuse=False):
        with tf.variable_scope(model_name, reuse=reuse):

            with tf.variable_scope("embedding") as vs:
                net_encode = EmbeddingInputlayer(
                    inputs=encode_seqs,
                    vocabulary_size = self.vocab_size,
                    embedding_size = 200,
                    name='seq_embedding')
                vs.reuse_variables()
                tl.layers.set_name_reuse(True)  # remove if TL version == 1.8.0+
                net_decode = EmbeddingInputlayer(
                    inputs=decode_seqs,
                    vocabulary_size = self.vocab_size,
                    embedding_size = 200,
                    name='seq_embedding')

            net_seq2seq = Seq2Seq(net_encode, net_decode,
                cell_fn = tf.contrib.rnn.BasicLSTMCell,
                n_hidden = 200,
                initializer = tf.random_uniform_initializer(-0.1, 0.1),
                encode_sequence_length = retrieve_seq_length_op2(encode_seqs),
                decode_sequence_length = retrieve_seq_length_op2(decode_seqs),
                initial_state_encode = None,
                dropout = None,
                n_layer = 1,
                return_seq_2d = True,
                name = 'seq2seq')
            net_out = DenseLayer(net_seq2seq, n_units=config.vocab_size, act=tf.identity, name='output')

        return net_out, net_seq2seq


    def __create_loss__(self):
        self.train_loss = tl.cost.cross_entropy_seq_with_mask(
            logits=self.train_net.outputs,
            target_seqs=self.target_seqs,
            input_mask=self.target_mask,
            return_details=False,
            name='train_loss'
        )
        self.test_loss = tl.cost.cross_entropy_seq_with_mask(
            logits=self.test_net.outputs,
            target_seqs=self.target_seqs,
            input_mask=self.target_mask,
            return_details=False,
            name='test_loss'
        )

    def __create_training_op__(self):
        self.global_step = tf.placeholder(
            dtype=tf.int32,
            shape=[],
            name="global_step"
        )
        self.learning_rate = tf.train.exponential_decay(
            learning_rate=self.start_learning_rate,
            global_step=self.global_step,
            decay_steps=self.decay_steps,
            decay_rate=self.decay_rate,
            staircase=True,
            name="learning_rate"
        )
        self.optim = tf.train.AdamOptimizer(self.learning_rate, beta1=0.5) \
            .minimize(self.train_loss, var_list=self.train_net.all_params)


if __name__ == "__main__":
    model = Model4Text(
        model_name="text_encoding",
        start_learning_rate=0.001,
        decay_rate=0.8,
        decay_steps=1000
    )
    pass