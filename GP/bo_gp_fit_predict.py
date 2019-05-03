# Copyright Lee Group 2019
# Author: Ryan-Rhys Griffiths
"""
This module contains GP fit and predict functions for use in Bayesian Optimisation. Compared to the gp_fitting module
the fitting and predict functions have been separated.
"""

import numpy as np
from scipy.optimize import minimize

from kernels import scipy_kernel
from utils import nll_fn, posterior_predictive, zero_mean


def bo_fit_homo_gp(xs, ys, noise, l_init, sigma_f_init):
    """
    Fit a homoscedastic GP to data (xs, ys) and return the optimised hypers.

    :param xs: sample locations N x D
    :param ys: sample labels
    :param noise: fixed noise level or noise function
    :param l_init: lengthscale(s) to initialise the optimiser
    :param sigma_f_init: signal amplitude to initialise the optimiser
    :return: Optimised kernel hyperparaemters.
    """

    dimensionality = xs.shape[1]  # Extract the dimensionality of the input so that lengthscales are appropriate dimension
    hypers = [l_init]*dimensionality + [sigma_f_init]  # we initialise each dimension with the same lengthscale value
    bounds = [(1e-2, 900)]*len(hypers)  # we initialise the bounds to be the same in each case

    # We fit GP1 to the data

    res = minimize(nll_fn(xs, ys, noise), hypers, bounds=bounds, method='L-BFGS-B')

    l_opt = np.array(res.x[:-1]).reshape(-1, 1)
    sigma_f_opt = res.x[-1]

    return l_opt, sigma_f_opt


def bo_predict_homo_gp(xs, ys, xs_star, noise, l_opt, sigma_f_opt):
    """
    Compute predictions at new test locations xs_star for the homoscedastic GP.

    :param xs: sample locations (m x d)
    :param ys: sample labels (m x 1)
    :param xs_star: test locations (n x d)
    :param noise: fixed noise level or noise function
    :param l_opt: optimised kernel lengthscale
    :param sigma_f_opt: optimised kernel signal amplitude
    :return: predictive mean and variance
    """

    pred_mean, pred_var, _, _ = posterior_predictive(xs, ys, xs_star, noise, l_opt, sigma_f_opt, mean_func=zero_mean, kernel=scipy_kernel)

    return pred_mean, pred_var


def bo_fit_hetero_gp(xs, ys, noise, l_init, sigma_f_init, l_noise_init, sigma_f_noise_init, gp2_noise, num_iters, sample_size):
    """
    Fit a heteroscedastic GP to data (xs, ys).

    :param xs: sample locations (m x d)
    :param ys: sample labels (m x 1)
    :param noise: fixed noise level or noise function
    :param l_init: lengthscale(s) to initialise the optimiser
    :param sigma_f_init: signal amplitude to initialise the optimiser
    :param l_noise_init: lengthscale(s) to initialise the optimiser for the noise
    :param sigma_f_noise_init: signal amplitude to initialise the optimiser for the noise
    :param gp2_noise: the noise level for the second GP modelling the noise (noise of the noise)
    :param num_iters: number of iterations to run the most likely heteroscedastic GP algorithm.
    :param sample_size: the number of samples for the heteroscedastic GP algorithm.
    :return: The noise function, variance estimator and GP1 and GP2 hypers.
    """

    dimensionality = xs.shape[1]  # in order to plot only in the 1D input case.
    gp1_hypers = [l_init]*dimensionality + [sigma_f_init]  # we initialise each dimension with the same lengthscale value
    gp2_hypers = [l_noise_init]*dimensionality + [sigma_f_noise_init]  # we initialise each dimensions with the same lengthscale value for gp2 as well.
    bounds = [(1e-2, 900)]*len(gp1_hypers)  # we initialise the bounds to be the same in each case

    for i in range(0, num_iters):

        # We fit GP1 to the data

        gp1_res = minimize(nll_fn(xs, ys, noise), gp1_hypers, bounds=bounds, method='L-BFGS-B')
        gp1_l_opt = np.array(gp1_res.x[:-1]).reshape(-1, 1)
        gp1_sigma_f_opt = gp1_res.x[-1]
        gp1_hypers = list(np.ndarray.flatten(gp1_l_opt)) + [gp1_sigma_f_opt]  # we initialise the optimisation at the next iteration with the optimised hypers

        # We compute the posterior predictive at the test locations

        gp1_pred_mean, gp1_pred_var = bo_predict_homo_gp(xs, ys, xs, noise, gp1_l_opt, gp1_sigma_f_opt)

        # We construct the most likely heteroscedastic GP noise estimator

        sample_matrix = np.zeros((len(ys), sample_size))
        for j in range(0, sample_size):
            sample_matrix[:, j] = np.random.multivariate_normal(gp1_pred_mean.reshape(len(gp1_pred_mean)), gp1_pred_var)
        variance_estimator = (0.5 / sample_size) * np.sum((ys - sample_matrix) ** 2, axis=1)  # Equation given in section 4 of Kersting et al. vector of noise for each data point.
        variance_estimator = np.log(variance_estimator)

        # We fit a second GP to the auxiliary dataset z = (xs, variance_estimator)

        gp2_res = minimize(nll_fn(xs, variance_estimator, gp2_noise), gp2_hypers, bounds=bounds, method='L-BFGS-B')
        gp2_l_opt = np.array(gp2_res.x[:-1]).reshape(-1, 1)
        gp2_sigma_f_opt = gp2_res.x[-1]
        gp2_hypers = list(np.ndarray.flatten(gp2_l_opt)) + [gp2_sigma_f_opt]  # we initialise the optimisation at the next iteration with the optimised hypers

        # we reshape the variance estimator here so that it can be passed into posterior_predictive.

        variance_estimator = variance_estimator.reshape(len(variance_estimator), 1)
        gp2_pred_mean, gp2_pred_var = bo_predict_homo_gp(xs, variance_estimator, xs, gp2_noise, gp2_l_opt, gp2_sigma_f_opt)
        gp2_pred_mean = np.exp(gp2_pred_mean)
        noise = np.sqrt(gp2_pred_mean)

    return noise, gp2_noise, gp1_l_opt, gp1_sigma_f_opt, gp2_l_opt, gp2_sigma_f_opt, variance_estimator


def bo_predict_hetero_gp(xs, ys, variance_estimator, xs_star, noise_func, gp1_l_opt, gp1_sigma_f_opt, gp2_noise, gp2_l_opt, gp2_sigma_f_opt):
    """
    Compute predictions at the test locations using the heteroscedastic GP.

    :param xs: sample locations (m x d)
    :param ys: sample labels (m x 1)
    :param variance_estimator: estimated variance at sample locations (m x 1)
    :param xs_star: test locations (n x d)
    :param noise_func: learned noise function
    :param gp1_l_opt: optimised lengthscale(s) of GP1
    :param gp1_sigma_f_opt: optimised signal amplitude of GP1
    :param gp2_noise: noise level of GP2
    :param gp2_l_opt: optimised lengthscale(s) of GP2
    :param gp2_sigma_f_opt: optimised signal amplitude of GP2
    :return: predictive mean and variance of the heteroscedastic GP at the test locations xs_star.
    """

    pred_mean_het, pred_var_het, _, _ = posterior_predictive(xs, ys, xs_star, noise_func, gp1_l_opt, gp1_sigma_f_opt)
    pred_mean_noise, _, _, _ = posterior_predictive(xs, variance_estimator, xs_star, gp2_noise, gp2_l_opt, gp2_sigma_f_opt)
    pred_mean_noise = np.exp(pred_mean_noise)
    pred_mean_noise = np.sqrt(pred_mean_noise).reshape(len(pred_mean_noise))  # taking the standard deviation

    pred_mean = pred_mean_het
    pred_var = np.diag(pred_var_het) + pred_mean_noise

    return pred_mean, pred_var, pred_mean_noise