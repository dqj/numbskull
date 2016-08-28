"""TODO."""

from __future__ import print_function
import numpy as np
from inference import *
from learning import *
from timer import Timer
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor


def run_pool(threadpool, threads, func, args):
    """TODO."""
    if threads == 1:
        func(0, *args)
    else:
        future_to_samples = \
            [threadpool.submit(func, threadID, *args)
             for threadID in range(threads)]
        concurrent.futures.wait(future_to_samples)
        for fts in future_to_samples:
            if fts.exception() is not None:
                raise fts.exception()


class FactorGraph(object):
    """TODO."""

    def __init__(self, weight, variable, factor, fstart, fmap, vstart, vmap,
                 equalPredicate, var_copies, weight_copies, fid, workers):
        """TODO."""
        self.weight = weight
        self.variable = variable
        self.factor = factor
        self.fstart = fstart
        self.fmap = fmap
        self.vstart = vstart
        self.vmap = vmap
        self.equalPred = equalPredicate

        # This is just cumsum shifted by 1
        self.cstart = np.zeros(self.variable.shape[0] + 1, np.int64)
        for i in range(self.variable.shape[0]):
            c = self.variable[i]["cardinality"]
            if c == 2:
                c = 1
            self.cstart[i + 1] = self.cstart[i] + c
        self.count = np.zeros(self.cstart[self.variable.shape[0]], np.int64)

        self.var_value = \
            np.tile(self.variable[:]['initialValue'], (var_copies, 1))
        self.weight_value = \
            np.tile(self.weight[:]['initialValue'], (weight_copies, 1))

        self.Z = np.zeros(max(self.variable[:]['cardinality']))

        self.fid = fid
        assert(workers > 0)
        self.threads = workers
        self.threadpool = ThreadPoolExecutor(self.threads)
        self.inference_epoch_time = 0.0
        self.inference_total_time = 0.0
        self.learning_epoch_time = 0.0
        self.learning_total_time = 0.0

    def clear(self):
        """TODO."""
        self.count[:] = 0
        self.threadpool.shutdown()

    #################
    #    GETTERS    #
    #################

    def getWeights(self, weight_copy=0):
        """TODO."""
        return self.weight_value[weight_copy][:]

    #####################
    #    DIAGNOSTICS    #
    #####################

    def diagnostics(self, epochs):
        """TODO."""
        print('Inference took %.03f sec.' % self.inference_total_time)
        bins = 10
        hist = np.zeros(bins, dtype=np.int64)
        for i in range(len(self.count)):
            hist[min(self.count[i] * bins / epochs, bins - 1)] += 1
        for i in range(bins):
            print(i, hist[i])

    def diagnosticsLearning(self, weight_copy=0):
        """TODO."""
        print('Learning epoch took %.03f sec.' % self.learning_epoch_time)
        print("Weights:")
        for (i, w) in enumerate(self.weight):
            print("    weightId:", i)
            print("        isFixed:", w["isFixed"])
            print("        weight: ", self.weight_value[weight_copy][i])
            print()

    ################################
    #    INFERENCE AND LEARNING    #
    ################################

    def burnIn(self, epochs, var_copy=0, weight_copy=0):
        """TODO."""
        print ("FACTOR " + str(self.fid) + ": STARTED BURN-IN...")
        shardID, nshards = 0, 1
        # NUMBA-based method. Implemented in inference.py
        gibbsthread(shardID, nshards, epochs, var_copy, weight_copy,
                    self.weight, self.variable, self.factor,
                    self.fstart, self.fmap, self.vstart, self.vmap,
                    self.equalPred, self.Z, self.cstart, self.count,
                    self.var_value, self.weight_value, True)
        print ("FACTOR " + str(self.fid) + ": DONE WITH BURN-IN")

    def inference(self, burnin_epochs, epochs, diagnostics=False,
                  var_copy=0, weight_copy=0):
        """TODO."""
        # Burn-in
        if burnin_epochs > 0:
            self.burnIn(burnin_epochs)

        # Run inference
        print ("FACTOR " + str(self.fid) + ": STARTED INFERENCE")
        for ep in range(epochs):
            with Timer() as timer:
                args = (self.threads, var_copy, weight_copy, self.weight,
                        self.variable, self.factor, self.fstart, self.fmap,
                        self.vstart, self.vmap, self.equalPred, self.Z,
                        self.cstart, self.count, self.var_value,
                        self.weight_value, False)
                run_pool(self.threadpool, self.threads, gibbsthread, args)
            self.inference_epoch_time = timer.interval
            self.inference_total_time += timer.interval
            if diagnostics:
                print('Inference epoch took %.03f sec.' %
                      self.inference_epoch_time)
        print ("FACTOR " + str(self.fid) + ": DONE WITH INFERENCE")
        if diagnostics:
            self.diagnostics(epochs)

    def learn(self, burnin_epochs, epochs, stepsize, decay,
              regularization, reg_param, diagnostics=False,
              learn_non_evidence=False, var_copy=0, weight_copy=0):
        """TODO."""
        # Burn-in
        if burnin_epochs > 0:
            self.burnIn(burnin_epochs)

        # Run learning
        print ("FACTOR " + str(self.fid) + ": STARTED LEARNING")
        for ep in range(epochs):
            with Timer() as timer:
                args = (self.threads, stepsize, regularization, reg_param,
                        var_copy, weight_copy, self.weight, self.variable,
                        self.factor, self.fstart, self.fmap, self.vstart,
                        self.vmap, self.equalPred, self.Z, self.var_value,
                        self.weight_value, learn_non_evidence)
                run_pool(self.threadpool, self.threads, learnthread, args)
            self.learning_epoch_time = timer.interval
            self.learning_total_time += timer.interval
            # Decay stepsize
            stepsize *= decay
            if diagnostics:
                print ("FACTOR " + str(self.fid) + ": EPOCH " + str(ep))
                print ("Current stepsize = "+str(stepsize))
                self.diagnosticsLearning(weight_copy)
        print ("FACTOR " + str(self.fid) + ": DONE WITH LEARNING")
