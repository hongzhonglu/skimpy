# -*- coding: utf-8 -*-
"""
.. module:: skimpy
   :platform: Unix, Windows
   :synopsis: Simple Kinetic Models in Python

.. moduleauthor:: SKiMPy team

[---------]

Copyright 2017 Laboratory of Computational Systems Biotechnology (LCSB),
Ecole Polytechnique Federale de Lausanne (EPFL), Switzerland

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIE CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""
from collections import namedtuple
import numpy as np
#from scipy.sparse.linalg import eigs as eigenvalues
from scipy.linalg import eigvals as eigenvalues
from sympy import sympify, Symbol

from skimpy.sampling.utils import calc_max_eigenvalue, calc_parameters
from skimpy.utils.namespace import *

import random, array
from deap import algorithms



from skimpy.sampling import ParameterSampler, SaturationParameterFunction, FluxParameterFunction


class GaParameterSampler(ParameterSampler):
    """
    A simple parameter sampler that samples stable model parameters
    with respect to a steady state flux and concentration state
    """

    Parameters = namedtuple('Parameters', ['n_samples'])
    # TODO Talk to Pierre / Misko about simple sampler parameters
    # if parameters are not defined put default values
    Parameters.__new__.__defaults__ = (None,) * len(Parameters._fields)

    def sample(self,
               compiled_model,
               flux_dict,
               concentration_dict,
               seed=123,
               max_generation=10,
               mutation_probability = 0.2,
               eta = 20,
               max_eigenvalue = 0,
               ):

        """

        :param compiled_model:
        :param flux_dict:
        :param concentration_dict:
        :param seed:
        :param max_generation:
        :param mutation_probability:
        :param eta:
        :return:
        """
        #
        from deap import base
        from deap import creator
        from deap import tools

        self.seed = seed
        random.seed(self.seed)

        symbolic_concentrations_dict = {Symbol(k):v
                                        for k,v in concentration_dict.items()}

        #Compile functions
        self._compile_sampling_functions(
            compiled_model,
            symbolic_concentrations_dict,
            flux_dict)

        """
        """

        self.compiled_model = compiled_model
        self.concentration_dict = concentration_dict
        self.flux_dict= flux_dict

        self.max_eigenvalue = max_eigenvalue

        """
        Define the DA optimzation problem with DEAP NSGA-2
        """

        creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
        creator.create("Individual", array.array, typecode='d', fitness=creator.FitnessMin)

        n_dim = len(compiled_model.saturation_parameter_function.sym_saturations)
        bound_low = [0.0,]*n_dim
        bound_up  = [1.0,]*n_dim

        toolbox = base.Toolbox()
        toolbox.register("attr_float", init_parameters, bound_low, bound_up)
        toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.attr_float)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)

        #if hasattr(compiled_model,'pool'):
        #    toolbox.register("map", compiled_model.pool.map)


        toolbox.register("evaluate", self.fitness)

        toolbox.register("mate", tools.cxSimulatedBinaryBounded, low=list(bound_low), up=list(bound_up), eta=eta)
        toolbox.register("mutate", tools.mutPolynomialBounded, low=list(bound_low), up=list(bound_up), eta=eta, indpb=1.0/n_dim)
        toolbox.register("select", tools.selBest)

        """
        """
        toolbox.pop_size = self.parameters.n_samples
        toolbox.max_gen = max_generation
        toolbox.mut_prob = mutation_probability

        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("std", np.std)
        stats.register("min", np.min)
        stats.register("max", np.max)

        result_saturations, log = run_ea(toolbox, stats=stats, verbose=True)

        parameter_population = []

        for this_sat in result_saturations:
            parameter_population.append(calc_parameters(this_sat,
                                                        compiled_model,
                                                        concentration_dict,
                                                        flux_dict)
                                        )
        # Plot pareto fronts

        return parameter_population

    # Under construction new sampling with compiled function
    def _compile_sampling_functions(self,model,
                                    concentrations,
                                    fluxes):
        """
        Compliles the function for sampling using theano
        :param model:
        """

        model.saturation_parameter_function = SaturationParameterFunction(model,
                                                                          model.parameters,
                                                                         concentrations)

        model.flux_parameter_function = FluxParameterFunction(model,
                                                              model.parameters,
                                                              concentrations,)

    def fitness(self,saturations):
        parameter_sample = calc_parameters(saturations,
                                           self.compiled_model,
                                           self.concentration_dict,
                                           self.flux_dict)

        lambda_max = calc_max_eigenvalue(parameter_sample,
                                         self.compiled_model,
                                         self.concentration_dict,
                                         self.flux_dict)
        if lambda_max < self.max_eigenvalue :

            return (self.max_eigenvalue,)
        else :
            return (lambda_max,)


"""
Utils
"""


def run_ea(toolbox, stats=None, verbose=False):
    pop = toolbox.population(n=toolbox.pop_size)
    pop = toolbox.select(pop, len(pop))
    return algorithms.eaMuPlusLambda(pop, toolbox, mu=toolbox.pop_size,
                                     lambda_=toolbox.pop_size,
                                     cxpb=1-toolbox.mut_prob,
                                     mutpb=toolbox.mut_prob,
                                     stats=stats,
                                     ngen=toolbox.max_gen,
                                     verbose=verbose)


"""
From DEAP tutorial 
"""
def init_parameters(low, up):
       return [random.uniform(a, b) for a, b in zip(low, up)]

def pareto_dominance(x,y):
    return tools.emo.isDominated(x.fitness.values, y.fitness.values)
