import tensorflow as tf
import tensorlayer as tl
from tensorlayer.layers import *
import numpy as np
import time

# --------------------- Global Variables ----------------------
batch_size = 50
v_t_dim = 300
v_c_dim = 300
lr = 0.0001 # Learning rate for Adam optimizer
n_epoch = 500

# --------------------- Model ---------------------------------
g = tf.Graph()
with g.as_default() as graph:
	v_t = tf.placeholder(dtype = tf.float32, shape = [None, v_t_dim], name = "text_vectors")
	v_c = tf.placeholder(dtype = tf.float32, shape = [None, v_c_dim], name = "class_vectors")
	y = tf.placeholder(dtype = tf.int64, shape = [None, None], name = "answer_vectors")
	M = tf.Variable(tf.random_uniform([v_t_dim, v_c_dim], dtype=tf.float32), name = "bilinear_matrix")
	h = tf.matmul(tf.matmul(v_t, M) , tf.transpose(v_c))
	prob_sigmoid = tf.sigmoid(h)
	predicted_answer = tf.round(prob_sigmoid)

# --------------------- Optimizer -----------------------------
with g.as_default() as graph:
	loss = tf.losses.sigmoid_cross_entropy(multi_class_labels = y, logits = h)
	train_op = tf.train.AdamOptimizer(learning_rate = lr).minimize(loss)
	print_all_variables(train_only=True)
	sess = tf.Session(config=tf.ConfigProto(allow_soft_placement=True, log_device_placement=False))

# --------------------- Training ------------------------------
def train_model(V_T_train, V_C_train, Y_train, dataset_name):
	with g.as_default() as graph:
		tl.layers.initialize_global_variables(sess)
		n_step = int(len(V_T_train)/batch_size)
		for epoch in range(n_epoch):
			epoch_time = time.time()

			# Train an epoch
			total_err, n_iter = 0, 0
			for X, Y in tl.iterate.minibatches(inputs = V_T_train, targets = Y_train, batch_size = batch_size, shuffle = True):
				step_time = time.time()
				_, err = sess.run([train_op, loss],
								{v_t: X,
								v_c: V_C_train,
								y: Y})

				if n_iter % 10 == 0:
					print("Epoch[%d/%d] step:[%d/%d] loss:%f took:%.5fs" % (epoch, n_epoch, n_iter, n_step, err, time.time() - step_time))
				
				total_err += err
				n_iter += 1
				
			print("Epoch[%d/%d] averaged loss:%f took:%.5fs" % (epoch, n_epoch, total_err/n_iter, time.time()-epoch_time))
			
			# Save trained parameters after running each epoch
			param = get_variables_with_name(name='bilinear_matrix:0')
			tl.files.save_npz(param, name='bilinear_matrix_' + dataset_name + '.npz', sess=sess)

# --------------------- Testing -------------------------------
def predict(V_T_test, V_C_test):
	with g.as_default() as graph:
		h_predict = sess.run(predicted_answer, {v_t: V_T_test, v_c: V_C_test})
		return h_predict

def test_model(V_T_test, V_C_test, Y_test, dataset_name):
	h_predict = predict(V_T_test, V_C_test)
	stats = get_statistics(h_predict, Y_test)
	print(stats)
	return stats

def get_statistics(prediction, ground_truth):
	assert prediction.shape == ground_truth.shape
	num_instance = prediction.shape[0]
	num_class = prediction.shape[1]

	# Accuracy
	accuracy = np.sum(prediction == ground_truth) / (num_instance*num_class)

	# Micro-average
	microP, microR, microF1 = get_precision_recall_f1(np.ravel(prediction), np.ravel(ground_truth))

	# Macro-average
	precisionList = []
	recallList = []
	for j in range(num_class): # Calculate Precision and Recall for class j
		p, r, _ = get_precision_recall_f1(prediction[:,j], ground_truth[:,j]) 
		precisionList.append(p)
		recallList.append(r)
	macroP = np.mean(np.array(precisionList))
	macroR = np.mean(np.array(recallList))
	macroF1 = 2 * macroP * macroR / (macroP + macroR)

	# Return stats results
	stats = {'accuracy': accuracy,
			'micro-precision': microP,
			'micro-recall': microR,
			'micro-F1': microF1,
			'macro-precision': macroP,
			'macro-recall': macroR,
			'macro-F1': macroF1,}
	return stats

def get_precision_recall_f1(prediction, ground_truth): # 1D data
	assert prediction.shape == ground_truth.shape and prediction.ndim == 1
	TP, FP, FN = 0, 0, 0
	for i in range(len(prediction)):
		if prediction[i] == 1 and ground_truth[i] == 1:
			TP += 1
		elif prediction[i] == 1 and ground_truth[i] == 0:
			FP += 1
		elif prediction[i] == 0 and ground_truth[i] == 1:
			FN += 1
	P = TP / (TP + FP)
	R = TP / (TP + FN)
	F1 = 2 * P * R / (P + R)
	return P, R, F1

# --------------------- Helper functions ----------------------
def get_pseudo_data(num_instance = 1000, num_class = 10, isTrain = True):
	positive_rate = 0.3
	V_T = np.random.rand(num_instance, v_t_dim)
	V_C = np.random.rand(num_class, v_c_dim)
	if isTrain:	
		Y_train = np.array([[1 if np.random.rand(1) < positive_rate else 0 for j in range(num_class)] for i in range(num_instance)])
		return V_T, V_C, Y_train
	else:
		return V_T, V_C

# --------------------- Main Operation ------------------------
if __name__ == "__main__":
	V_T_train, V_C_train, Y_train = get_pseudo_data()
	train_model(V_T_train, V_C_train, Y_train, 'pseudo')
	V_T_test, V_C_test = get_pseudo_data(num_instance = 20, num_class = 5, isTrain = False)
	print(predict(V_T_test, V_C_test))
	test_model(V_T_train, V_C_train, Y_train, 'pseudo') # Test with training data
	V_T_train, V_C_train, Y_train = get_pseudo_data()
	test_model(V_T_train, V_C_train, Y_train, 'pseudo')