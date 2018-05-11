import os
import random
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import time
import numpy as np
import pandas as pd
import tensorflow as tf
import tensorlayer as tl
from datetime import datetime, timedelta
from random import randint

import utils
import config
import model
import dataloader

results_path = "../results/"

class Controller():

    def __init__(self, model):
        self.model = model
        self.saver = tf.train.Saver(max_to_keep=200)
        self.sess = tf.Session()
        tl.layers.initialize_global_variables(self.sess)
        self.__init_path__()
        self.__init_mkdir__()

    def __init_path__(self):
        self.model_save_dir = "%s/%s/models/" % (results_path, self.model.model_name)
        self.log_save_dir = "%s/%s/logs/" % (results_path, self.model.model_name)
        self.figs_save_dir = "%s/%s/figs/" % (results_path, self.model.model_name)

    def __init_mkdir__(self):
        dirlist = [
            self.model_save_dir,
            self.log_save_dir,
            self.figs_save_dir
        ]
        utils.make_dirlist(dirlist)

    def save_model(self, path, global_step=None):
        save_path = self.saver.save(self.sess, path, global_step=global_step)
        print("[S] Model saved in ckpt %s" % save_path)
        return save_path

    def restore_model(self, path, global_step=None):
        model_path = "%s-%s" % (path, global_step)
        self.saver.restore(self.sess, model_path)
        print("[R] Model restored from ckpt %s" % model_path)
        return True

    def save_model_npz_dict(self, path, global_step=None):
        name = "%s-%s.npz" % (path, global_step)
        save_list_names = [tensor.name for tensor in self.model.train_net.all_params]
        save_list_var = self.sess.run(self.model.train_net.all_params)
        save_var_dict = {save_list_names[idx]: val for idx, val in enumerate(save_list_var)}
        np.savez(name, **save_var_dict)
        save_list_var = None
        save_var_dict = None
        del save_list_var
        del save_var_dict
        print("[S] Model saved in npz_dict %s" % name)

    def load_assign_model_npz_dict(self, path, global_step=None):
        name = "%s-%s.npz" % (path, global_step)
        params = np.load(name)
        if len(params.keys()) != len(set(params.keys())):
            raise Exception("Duplication in model npz_dict %s" % name)
        ops = list()
        for key in params.keys():
            # tensor = tf.get_default_graph().get_tensor_by_name(key)
            varlist = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope=key)
            if len(varlist) > 1:
                raise Exception("Multiple candidate variables to be assigned for name %s" % key)
            elif len(varlist) == 0:
                print("Warning: Tensor named %s not found in network." % key)
            else:
                ops.append(varlist[0].assign(params[key]))
                print("[R] Tensor restored: %s" % key)

        self.sess.run(ops)
        print("[R] Model restored from npz_dict %s" % name)


class Controller_KG4Text(Controller):

    def __init__(
            self,
            model,
            base_epoch
    ):
        Controller.__init__(self, model=model)
        self.base_epoch = base_epoch

    def __run__(self, epoch, text_seqs, vocab, kg_vector_dict, class_list, class_dict, mode):

        assert len(text_seqs) == len(class_list)

        train_order = list(range(len(text_seqs)))

        if mode == "train":
            random.shuffle(train_order)

        start_time = time.time()
        step_time = time.time()

        all_loss = np.zeros(1)

        train_steps = len(train_order) // config.batch_size

        for cstep in range(train_steps):

            text_seqs_mini = [text_seqs[idx] for idx in train_order[cstep * config.batch_size : (cstep + 1) * config.batch_size]]
            true_class_mini = [class_list[idx] for idx in train_order[cstep * config.batch_size : (cstep + 1) * config.batch_size]]
            category_logits = [randint(0, 1) for b in range(config.batch_size)]
            # category_logits = [1] * config.batch_size

            encode_seqs_mini = dataloader.prepro_encode(text_seqs_mini.copy(), vocab)

            kg_vector_seqs_mini = dataloader.get_kg_vector_sentence(encode_seqs_mini, true_class_mini, class_dict, category_logits, kg_vector_dict, vocab)

            # for i in range(config.batch_size):
            #     print(category_logits[i], true_class_mini[i], np.sum(kg_vector_seqs_mini[i]))
            # exit()

            global_step = cstep + epoch * train_steps

            if mode == "train":
                results = self.sess.run([
                    self.model.train_loss,
                    self.model.learning_rate,
                    self.model.optim
                ], feed_dict={
                    self.model.encode_seqs: encode_seqs_mini,
                    self.model.kg_vector: kg_vector_seqs_mini,
                    self.model.category_logits: np.expand_dims(category_logits, -1),
                    self.model.global_step: global_step,
                })

            elif mode == "test":
                results = self.sess.run([
                    self.model.test_loss,
                    tf.constant(-1),
                    tf.constant(-1)
                ], feed_dict={
                    self.model.encode_seqs: encode_seqs_mini,
                    self.model.kg_vector: kg_vector_seqs_mini,
                    self.model.category_logits: np.expand_dims(category_logits, -1),
                })

            all_loss += results[:1]

            if cstep % 100 == 0 and cstep > 0:
                print(
                    "[T%s] Epoch: [%3d][%4d/%4d] time: %.4f, lr: %.8f, loss: %s" %
                    (mode[1:], epoch, cstep, train_steps, time.time() - step_time, results[-2], all_loss / (cstep + 1))
                )
                step_time = time.time()

        print(
            "[T%s Sum] Epoch: [%3d] time: %.4f, lr: %.8f, loss: %s" %
            (mode[1:], epoch, time.time() - start_time, results[-2], all_loss / train_steps)
        )

        return all_loss / train_steps


    def __inference__(self, epoch, text_seqs, vocab, kg_vector_dict, class_list):

        assert len(text_seqs) == len(kg_vector_seqs)

        start_time = time.time()
        step_time = time.time()


        for cstep in range(len(text_seqs)):

            text_seqs_mini = text_seqs[cstep : cstep + 1]
            kg_vector_seqs_mini = kg_vector_seqs[cstep : cstep + 1]
            encode_seqs_mini = dataloader.prepro_encode(text_seqs_mini.copy(), vocab)
            encode_kg_vector_seqs_mini = dataloader.prepro_encode_kg_vector(kg_vector_seqs_mini.copy())

            _ = self.sess.run(
                self.model.infer_lossj,
                feed_dict={
                    self.model.encode_seqs_infer: encode_seqs_mini,
                    self.model.kg_vector_infer: encode_kg_vector_seqs_mini,
                })

        return


    def controller(self, text_seqs, vocab, kg_vector_dict, class_list, class_dict, inference=False, train_epoch=config.train_epoch):

        if inference:
            assert self.base_epoch > 0

        last_save_epoch = self.base_epoch
        global_epoch = self.base_epoch + 1

        if last_save_epoch >= 0:
            self.restore_model(
                path=self.model_save_dir,
                global_step=last_save_epoch
            )

        if inference:

            # state = self.__inference__(global_epoch, text_seqs[:3], vocab, verify=False)
            # print(state.shape)
            # state = self.__inference__(global_epoch, text_seqs[-3:], vocab, verify=False)
            # print(state.shape)

            text_state1 = self.__run__(global_epoch, text_seqs[:], vocab, kg_vector_dict, class_list, class_dict, mode="test")  # inference by minibatch, so some seq will be missing

            if text_state1.shape[0] < len(text_seqs):
                text_state2 = self.__inference__(global_epoch, text_seqs[text_state1.shape[0]:], vocab) # those seq that was missing by minibatch
                text_state = np.concatenate((text_state1, text_state2), axis=0)
            else:
                text_state = text_state1

            assert text_state.shape == (len(text_seqs), config.hidden_dim)
            print("Text state ", text_state.shape)
            return text_state

        else:

            for epoch in range(train_epoch + 1):

                self.__run__(
                    global_epoch,
                    text_seqs[:-len(text_seqs) // 10],
                    vocab,
                    kg_vector_dict,
                    class_list[:-len(class_list) // 10],
                    class_dict,
                    mode="train"
                )
                self.__run__(
                    global_epoch,
                    text_seqs[-len(text_seqs) // 10:],
                    vocab,
                    kg_vector_dict,
                    class_list[-len(class_list) // 10:],
                    class_dict,
                    mode="test"
                )

                # self.__inference__(global_epoch, text_seqs[:3], vocab)
                # self.__inference__(global_epoch, text_seqs[-3:], vocab)

                if global_epoch > self.base_epoch and global_epoch % 1 == 0:
                    self.save_model(
                        path=self.model_save_dir,
                        global_step=global_epoch
                    )
                    last_save_epoch = global_epoch

                global_epoch += 1


if __name__ == "__main__":

    vocab = dataloader.build_vocabulary_from_full_corpus(
        config.zhang15_dbpedia_full_data_path, config.zhang15_dbpedia_vocab_path, column="text", force_process=False
    )

    kg_vector_dict = dataloader.load_kg_vector(config.kg_vector_data_path)

    class_dict = dataloader.load_class_dict(
        class_file=config.zhang15_dbpedia_class_label_path,
        class_code_column="ClassCode",
        class_name_column="ConceptNet"
    )

    train_class_list = dataloader.load_data_class(
        filename=config.zhang15_dbpedia_train_path,
        column="class",
    )

    train_text_seqs = dataloader.load_data_from_text_given_vocab(
        config.zhang15_dbpedia_train_path, vocab, config.zhang15_dbpedia_train_processed_path,
        column="text", force_process=False
    )

    # train_kg_vector = dataloader.load_kg_vector_given_text_seqs(
    #     train_text_seqs, vocab, class_dict, kg_vector_dict,
    #     processed_file=config.zhang15_dbpedia_kg_vector_train_processed_path,
    #     force_process=False
    # )

    # test_class_list = dataloader.load_data_class(
    #     filename=config.zhang15_dbpedia_test_path,
    #     column="class",
    # )

    # test_text_seqs = dataloader.load_data_from_text_given_vocab(
    #     config.zhang15_dbpedia_test_path, vocab, config.zhang15_dbpedia_test_processed_path,
    #     column="text", force_process=False
    # )

    # test_kg_vector = dataloader.load_kg_vector_given_text_seqs(
    #     test_text_seqs, vocab, class_dict, kg_vector_dict,
    #     processed_file=config.zhang15_dbpedia_kg_vector_test_processed_path,
    #     force_process=False
    # )

    with tf.Graph().as_default() as graph:
        tl.layers.clear_layers_name()
        mdl = model.Model_KG4Text(
            model_name="text_encoding_zhang15_dbpedia",
            start_learning_rate=0.0001,
            decay_rate=0.8,
            decay_steps=8e3,
            vocab_size=15000
        )
        ctl = Controller_KG4Text(model=mdl, base_epoch=-1)
        ctl.controller(train_text_seqs, vocab, kg_vector_dict, train_class_list, class_dict, train_epoch=20)

        # text_state = ctl.controller(train_text_seqs, vocab, inference=True)
        # np.savez(config.zhang15_dbpedia_train_state_npz_path, state=text_state)

        # text_state = ctl.controller(test_text_seqs, vocab, inference=True)
        # np.savez(config.zhang15_dbpedia_test_state_npz_path, state=text_state)

        ctl.sess.close()
    pass








