import pandas as pd
import numpy as np
import data
import layers
import tensorflow as tf
from sklearn.metrics import mean_squared_error
from sklearn.metrics import r2_score

def model_fn(features, mode, params):
    layer =layers.basic_layer(mode)
    
    fnames=[]
    for f in params.feature_name:
        fnames.append(features[f])
        
    x = tf.concat(fnames,axis=-1)
    timestep = tf.shape(x)[1]
    x = tf.reshape(x,[-1,timestep,params.dim])
    t = features['label']
    
    #for i,fsize in enumerate(params.denses):
        #x = layer.conv1d_layer(x, params.ksize, fsize, name='mfcc_%s' %i, bn=0, padding='same', strides=1, L2 = params.L2, dp = params.dropout,
              #act='relu', trainable=True, reuse = None)
    rate=1
    for i,fsize in enumerate(params.denses):
        if params.hole==1:
            x = layer.atrous_conv1d_layer(x, params.ksize, fsize, name='mfcc_%s_%s' %(i,rate), bn=0, padding='same', rate=rate, L2 = params.L2, dp = params.dropout,act='relu', trainable=True, reuse = None)
        else:
            x = layer.conv1d_layer(x, params.ksize, fsize, name='mfcc_%s' %i, bn=0, padding='same', strides=1, L2 = params.L2, dp = params.dropout,act='relu', trainable=True, reuse = None)
        if params.pooltype!='none':
            x =layer.downsampling1d(x, name='pool_%s' %i, ptype=params.pooltype, psize=2, strides=2)
        rate=rate*2
        
    x = layer.globalpool(x, ptype='avg',name='pool')
    
    o = tf.layers.dense(inputs=x, units=1, name= 'output')

    predictions = {"labels": t,"outputs": o,"hiddens": x}
    
    if mode == tf.estimator.ModeKeys.PREDICT:
        return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)
    

        
    loss = tf.losses.mean_squared_error(labels = t, predictions = o, scope='mse_loss')
    L2_loss = tf.losses.get_regularization_loss(scope='L2')
    
    total_loss = loss
    if params.L2>0:
        total_loss += L2_loss
        
    if mode == tf.estimator.ModeKeys.TRAIN:
        optimizer = tf.train.AdamOptimizer(learning_rate=params.learning_rate)
        train_op = optimizer.minimize(
        loss=total_loss,
        global_step=tf.train.get_global_step())
        return tf.estimator.EstimatorSpec(mode=mode, loss=total_loss, train_op=train_op)
    eval_metric_ops = {"rmse": tf.metrics.root_mean_squared_error(labels = t, predictions = o)}
    return tf.estimator.EstimatorSpec(mode=mode, loss=total_loss, eval_metric_ops=eval_metric_ops)

def input_fn(foldID, setname, feature_name, shuffle_buffer,batchsize=2,epoch=1,path='/home/jyu/haoweilai/tfrecords/',label_in_feature=True):
    # how many shards to use
    if setname =='test':
        shards=[foldID]
    elif setname =='train':
        shards=[i for i in range(7) if i!=foldID]
    elif setname =='predict':
        shards=list(range(7))
    # shapes
    fshapes={'IS10lld':{'IS10lld':[1000,76]},'IS10lld3':{'IS10lld3':[1000,76*3]},
          'IS13lld':{'IS13lld':[1000,130]},'IS13lld3':{'IS13lld3':[1000,130*3]},
          'mfcc':{'mfcc':[1000,39]},
          'fb':{'fb':[1000,123]}}
    
    # label
    dataset_paths=[]
    
    for s in shards:
        dataset_path = '%s/%s/%s.tfrecord' %(path, 'label', s)
        dataset_paths.append(dataset_path)
    print('label',shards)
    info_path = '%s/%s_info.csv' %(path, 'label')
    dataset = data.get_dataset(paths=dataset_paths, data_info=info_path, num_parallel_calls=4, prefetch_buffer=batchsize)
    
    datasets = [dataset]
    pad_shapes = [{'label':[1]}]
    #pad_shapes.append({'label':[None,1]})
    # feature sets
    for sn in feature_name:
        dataset_paths=[]
        for s in shards:
            dataset_path = '%s/%s/%s.tfrecord' %(path, sn, s)
            dataset_paths.append(dataset_path)
        pad_shapes.append(fshapes[sn])
        info_path = '%s/%s_info.csv' %(path, sn)
        dataset = data.get_dataset(paths=dataset_paths, data_info=info_path, num_parallel_calls=4, prefetch_buffer=batchsize)
        datasets.append(dataset)
        print(sn,shards)
    
        
    dataset = tf.data.Dataset.zip(tuple(datasets))
    if shuffle_buffer>1:
        dataset = dataset.shuffle(buffer_size=shuffle_buffer)
    dataset = dataset.padded_batch(batchsize, padded_shapes = tuple(pad_shapes))
    dataset = dataset.repeat(epoch)
    iterator = dataset.make_one_shot_iterator()
    example = iterator.get_next()
    
    features={}
    for i,sn in enumerate(feature_name):
        features[sn]=example[i+1][sn]
        
    if label_in_feature:
        print('label in features')
        features['label'] =example[0]['label']
        return features
    else:
        return (features,example[0]['label'])
    
def setparam():
        model_params = tf.contrib.training.HParams(
                                foldID=foldID,
                                feature_name = feature_name,
                                denses = denses,
                                L2 = L2,
                                dim=dim,
                                batchsize =batchsize,
                                dropout = dropout,
                                ksize=ksize,
                                pooltype=pooltype,
                                hole=hole,
                                learning_rate = learning_rate)
        return model_params
    
logpath = '/home/jyu/haoweilai/c1'
foldID=0
feature_name = ['IS09','IS10','IS13','IS16']
denses = [512,512,512,512]
L2 = 1e-4
batchsize = 2
dropout = 0
learning_rate = 5e-4
Epoch=100
n_example=1200
ksize=3
pooltype='max'
dim=39
hole = 1
#for feature_name,dim in zip([['fb'],['mfcc'],['fb','mfcc']],[123,39,123+39]):
#for feature_name,dim in zip([['mfcc','fb']],[123+39]):
for feature_name,dim in zip([['fb','IS10lld','IS13lld']],[123+130+76]):
    for denses in [[512,512,512,512]]:
        for batchsize in [32]:
            for learning_rate in [1e-4]:
                for dropout in [0]:
                    for pooltype in ['max']:
                        for hole in [1]:
                            for ksize in [3]:
                                rmses=[]
                                pccs=[]
                                for foldID in range(1):
                                    model_params = setparam()
                                    path_name_list = (model_params.foldID,hole,''.join([str(r) for r in feature_name]),ksize,pooltype,''.join([str(r) for r in model_params.denses]),model_params.L2,model_params.dropout,model_params.batchsize,model_params.learning_rate)
                                    path_name = logpath+"/id%s_h%s_f%s_k%s_p%s_d%s_L2%s_dp%s_b%s_l%s" %path_name_list
                                    myconfig = tf.estimator.RunConfig(
                                                            model_dir = path_name,
                                                            save_summary_steps=int(n_example/model_params.batchsize),
                                                            save_checkpoints_steps=int(n_example/model_params.batchsize),
                                                            save_checkpoints_secs=None,
                                                            session_config=None,
                                                            keep_checkpoint_max=1,
                                                            keep_checkpoint_every_n_hours=int(n_example/model_params.batchsize),
                                                            log_step_count_steps=int(n_example/model_params.batchsize))
                                    regressor = tf.estimator.Estimator(
                                                model_fn = model_fn,
                                                config = myconfig,
                                                params=model_params)
                                    train_spec = tf.estimator.TrainSpec(lambda: input_fn(foldID, 'train', feature_name, n_example,batchsize,1), max_steps=int(n_example/batchsize)*Epoch)
                                    eval_spec = tf.estimator.EvalSpec(lambda: input_fn(foldID, 'test', feature_name, 1,batchsize=batchsize))
                                    tf.estimator.train_and_evaluate(regressor, train_spec, eval_spec)
                                    predictions = list(regressor.predict(input_fn=lambda:input_fn(foldID, 'test', feature_name, 1)))
                                    P = np.array([p['outputs'] for p in predictions])
                                    L = np.array([p['labels'] for p in predictions])
                                    rmse=np.sqrt(mean_squared_error(L,P))
                                    pcc=np.sqrt(r2_score(L,P))
                                    rmses.append(rmse)
                                    pccs.append(pcc)
                                    print('rmse: %s | pcc: %s' %(rmse, pcc))
                                with open(logpath+'/eval.txt','a') as f:
                                    f.write('%s %s %s\n' %(path_name,np.array(rmses).mean(),np.array(pccs).mean()))
