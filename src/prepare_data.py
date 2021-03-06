import numpy as np
import os
import struct
from array import array as pyarray
from numpy import unique
import cPickle
from graph import Graph
from random import shuffle
from random import seed
from joblib import Parallel, delayed
import multiprocessing
import time
from sklearn.cross_validation import StratifiedKFold, StratifiedShuffleSplit
import pandas as pd
import argparse

import theano
import theano.tensor as T


parser = argparse.ArgumentParser(description="Prepare Data")
parser.add_argument("-m", "--method", default="CV", help="CV or Holdout method.") #Holdout method TBI
parser.add_argument("-d", "--dataset", default="Cirrhosis", help="Name of dataset in data folder.")
parser.add_argument("-n", "--splits", default=10, type=int, help="Number of cross validated splits.")
parser.add_argument("-s", "--sets", default=10, type=int, help="Number of datasets to generate")
args = parser.parse_args()


#Create Theano shared variables
def shared(data):
	shared_x = theano.shared(
		np.asarray(data[0], dtype=theano.config.floatX), borrow=True)
	shared_y = theano.shared(
		np.asarray(data[1], dtype=theano.config.floatX), borrow=True)
	return shared_x, T.cast(shared_y, "int32")
		
def shared2(datax, datay):
	return datax, T.cast(datay, "int32")

#Convert abundance vector into tree matrix
def generate_maps(x, g, f, p=-1):
	id = multiprocessing.Process()._identity	
	g.populate_graph(f, x)
	return x, np.array(g.get_map(p))


data = args.dataset
num_cores = multiprocessing.cpu_count()

if __name__ == "__main__":
	holdout_seed = 0
	for set in range(0,args.sets):
		dat_dir = "../data/" + data
		holdout_seed = holdout_seed + 1
		print("Processing " + data +"...")
		
		#Data Variables	
		my_x = []
		my_y = []
		
				
		#Get count matrices
		print ("Opening data files...") 
		print(data)
		my_x = np.loadtxt(dat_dir + '/count_matrix.csv', dtype=np.float32, delimiter=',')
				
		#Get sample labels	
		my_y = np.genfromtxt(dat_dir + '/labels.txt', dtype=np.str_, delimiter=',')
			
		#Get the list of OTUs			
		features = np.genfromtxt(dat_dir+ '/otu.csv', dtype=np.str_, delimiter=',')
			
		print("Finished reading data...")
			
		num_samples = my_x.shape[0]
		num_features = len(my_x[0])
		#Get the set of classes	
		classes = list(unique(my_y))
		num_classes = len(classes)
		print("There are " + str(num_classes) + " classes")  
		my_ref = pd.factorize(my_y)[1]
		f = open(dat_dir + "/label_reference.txt", 'w')
		f.write(str(my_ref))
		f.close()
		
		#Build phylogenetic tree graph
		g = Graph()
		g.build_graph(dat_dir + "/newick.txt")
		print("Graph constructed...")
		#Create 10 CV sets
		print("Generating set " + str(set) + "...")
		
		my_data = pd.DataFrame(my_x)
		my_data = np.array(my_data)
		my_lab = pd.factorize(my_y)[0]
		my_maps = []
		my_benchmark = []
		
		results = Parallel(n_jobs=num_cores)(delayed(generate_maps)(x,g,features) for x in my_data)
		my_maps = np.array(np.take(results,1,1).tolist())
		my_benchmark = np.array(np.take(results,0,1).tolist())
										 
		my_maps = np.array(my_maps)
		my_benchmark = np.array(my_benchmark)				
		map_rows = my_maps.shape[1]
		map_cols = my_maps.shape[2]
			
		print("Finished Setup...") 
		
		if args.method=="CV":
			k_fold = StratifiedKFold(my_lab, n_folds=args.splits, shuffle=True)		
			count = 0
			#for train_index, test_index in kf.split(my_maps[0], my_lab):
			for train_index, test_index in k_fold:
				x_train = []
				x_test = []
				y_train=[]
				y_test=[]
				benchmark_train=[]
				benchmark_test=[]
			
				print("Creating split " + str(count))
			
				x_train.append(my_maps[train_index])
				x_test.append(my_maps[test_index])
				y_train.append(my_lab[train_index])
				y_test.append(my_lab[test_index])
				benchmark_train.append(my_benchmark[train_index])
				benchmark_test.append(my_benchmark[test_index])
			

				x_train = np.array(x_train).reshape(-1, map_rows, map_cols)
				x_test = np.array(x_test).reshape(-1, map_rows, map_cols)
				y_train = np.squeeze(np.array(y_train).reshape(1,-1), 0)
				y_test = np.squeeze(np.array(y_test).reshape(1,-1), 0)
				benchmark_train = np.array(benchmark_train).reshape(-1, num_features)
				benchmark_test = np.array(benchmark_test).reshape(-1, num_features)
		   
				seed = np.random.randint(1000)
				np.random.seed(seed)
				np.random.shuffle(x_train)
				np.random.seed(2*seed)
				np.random.shuffle(x_test)
				np.random.seed(seed)
				np.random.shuffle(y_train)
				np.random.seed(2*seed)
				np.random.shuffle(y_test)
				np.random.seed(seed)
				np.random.shuffle(benchmark_train)
				np.random.seed(2*seed)
				np.random.shuffle(benchmark_test)
			
				#Combine data and labels into a single object
				x_train = theano.shared(x_train)
				y_train2 = theano.shared(y_train)
				x_test = theano.shared(x_test)
				y_test2 = theano.shared(y_test)
				train = shared2(x_train,y_train2)
				test = shared2(x_test, y_test2)
				
				dir = dat_dir + "/data_sets//CV_" + str(set) + "/" + str(count)
				if not os.path.exists(dir):
					os.makedirs(dir)
				
				#Save the data sets in Pickle format
				f = open(dir + "/training.save", 'wb')
				cPickle.dump(train, f, protocol=cPickle.HIGHEST_PROTOCOL)
				f.close()
				
				f = open(dir + "/test.save", 'wb')
				cPickle.dump(test, f, protocol=cPickle.HIGHEST_PROTOCOL)
				f.close()
				
				f = open(dir + "/validation.save", 'wb')
				cPickle.dump(test, f, protocol=cPickle.HIGHEST_PROTOCOL)
				f.close()
				
			
				np.savetxt(dir + "/benchmark_train_data.csv", benchmark_train, delimiter=',')
				np.savetxt(dir + "/benchmark_train_labels.csv", y_train, delimiter=',')
				np.savetxt(dir + "/benchmark_test_data.csv", benchmark_test, delimiter=',')
				np.savetxt(dir + "/benchmark_test_labels.csv", y_test, delimiter=',')
				count = count + 1


		print("Finished Setup...")

		if args.method=="holdout" or args.method=="HO":						
			k_fold = StratifiedShuffleSplit(my_lab, n_iter=1,  test_size=0.3, random_state=holdout_seed)
			count = 0
			#for train_index, test_index in kf.split(my_maps[0], my_lab):
			for train_index, test_index in k_fold:
				x_train = []
				x_test = []
				x_valid = []
				y_train=[]
				y_test=[]
				y_valid = []

				benchmark_train=[]
				benchmark_test=[]
				benchmark_valid=[]


				test_valid_split = int(round(len(test_index) * 0.667))
				valid_index = test_index[(test_valid_split + 1):]
				test_index = test_index[:test_valid_split]

				print("Creating split " + str(count))

				x_train.append(my_maps[train_index])
				x_test.append(my_maps[test_index])
				x_valid.append(my_maps[valid_index])
				y_train.append(my_lab[train_index])
				y_test.append(my_lab[test_index])
				y_valid.append(my_lab[valid_index])
				benchmark_train.append(my_benchmark[train_index])
				benchmark_test.append(my_benchmark[test_index])
				benchmark_valid.append(my_benchmark[valid_index])

				x_train = np.array(x_train).reshape(-1, map_rows, map_cols)
				x_test = np.array(x_test).reshape(-1, map_rows, map_cols)
				x_valid = np.array(x_valid).reshape(-1, map_rows, map_cols)
				y_train = np.squeeze(np.array(y_train).reshape(1,-1), 0)
				y_test = np.squeeze(np.array(y_test).reshape(1,-1), 0)
				y_valid = np.squeeze(np.array(y_valid).reshape(1,-1), 0)
				benchmark_train = np.array(benchmark_train).reshape(-1, num_features)
				benchmark_test = np.array(benchmark_test).reshape(-1, num_features)
				benchmark_valid = np.array(benchmark_valid).reshape(-1, num_features)
 
				
				x_train = theano.shared(x_train)
				y_train2 = theano.shared(y_train)
				x_test = theano.shared(x_test)
				y_test2 = theano.shared(y_test)
				x_valid = theano.shared(x_valid)
				y_valid2 = theano.shared(y_valid)
				train = shared2(x_train,y_train2)
				test = shared2(x_test, y_test2)
				valid = shared2(x_valid, y_valid2)

				dir = dat_dir + "/data_sets/HO_" + str(set) + "/"
				if not os.path.exists(dir):
					os.makedirs(dir)

				#Save the data sets in Pickle format
				f = open(dir + "/training.save", 'wb')
				cPickle.dump(train, f, protocol=cPickle.HIGHEST_PROTOCOL)
				f.close()

				f = open(dir + "/test.save", 'wb')
				cPickle.dump(test, f, protocol=cPickle.HIGHEST_PROTOCOL)
				f.close()

				f = open(dir + "/validation.save", 'wb')
				cPickle.dump(valid, f, protocol=cPickle.HIGHEST_PROTOCOL)
				f.close()

				np.savetxt(dir + "/benchmark_train_data.csv", benchmark_train, delimiter=',')
				np.savetxt(dir + "/benchmark_train_labels.csv", y_train, delimiter=',')
				np.savetxt(dir + "/benchmark_test_data.csv", benchmark_test, delimiter=',')
				np.savetxt(dir + "/benchmark_test_labels.csv", y_test, delimiter=',')
				np.savetxt(dir + "/benchmark_valid_data.csv", benchmark_valid, delimiter=',')
				np.savetxt(dir + "/benchmark_valid_labels.csv", y_valid, delimiter=',')
				count = count + 1
	
			print("Finished writing files...")
