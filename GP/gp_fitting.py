# Copyright Lee Group 2019
# Author: Ryan-Rhys Griffiths
"""
This module contains GP-fitting procedures for the homoscedastic and heteroscedastic GP implementations.
"""

from matplotlib import pyplot as plt
import numpy as np
from scipy.optimize import minimize

from kernels import scipy_kernel
from mean_functions import zero_mean
from utils import neg_log_marg_lik_krasser, nll_fn, posterior_predictive_krasser, posterior_predictive


def fit_homo_gp(xs, ys, noise, xs_star, l_init, sigma_f_init, fplot=False):
    """
    Fit a homoscedastic GP to data (xs, ys) and compute the negative log predictive density at new input locations
    xs_star.

    :param xs: input locations N x D
    :param ys: target labels
    :param noise: fixed noise level or noise function
    :param xs_star: test input locations
    :param l_init: lengthscale(s) to initialise the optimiser
    :param sigma_f_init: signal amplitude to initialise the optimiser
    :param f_plot: bool indicating whether to plot the posterior predictive or not.
    :return: negative log marginal likelihood value and negative log predictive density.
    """

    dimensionality = xs.shape[1]  # Extract the dimensionality of the input so that lengthscales are appropriate dimension
    hypers = [l_init]*dimensionality + [sigma_f_init]  # we initialise each dimension with the same lengthscale value
    bounds = [(1e-2, 900)]*len(hypers)  # we initialise the bounds to be the same in each case

    # We fit GP1 to the data

    res = minimize(nll_fn(xs, ys, noise), hypers, bounds=bounds, method='L-BFGS-B')

    l_opt = np.array(res.x[:-1]).reshape(-1, 1)
    sigma_f_opt = res.x[-1]

    pred_mean, pred_var, _, _ = posterior_predictive(xs, ys, xs_star, noise, l_opt, sigma_f_opt, mean_func=zero_mean, kernel=scipy_kernel)
    nlml = neg_log_marg_lik_krasser(xs, ys, noise, l_opt, sigma_f_opt)  # measure nlml of hypers

    if fplot:
        plot_xs_star = xs_star.reshape(len(xs_star), )
        plot_pred_var = np.diag(pred_var).reshape(-1, 1)  # Take the diagonal of the covariance matrix for plotting purposes
        plt.plot(xs, ys, '+', color='green', markersize='12', linewidth='8')
        plt.plot(plot_xs_star, pred_mean, '-', color='red')
        upper = pred_mean + 2 * np.sqrt(plot_pred_var)
        lower = pred_mean - 2 * np.sqrt(plot_pred_var)
        upper = upper.reshape(plot_xs_star.shape)
        lower = lower.reshape(plot_xs_star.shape)
        plt.fill_between(plot_xs_star, upper, lower, color='gray', alpha=0.2)
        plt.xlabel('input, x')
        plt.ylabel('f(x)')
        plt.title('Homoscedastic GP Posterior')
        plt.show()

    return pred_mean, pred_var, nlml


def fit_hetero_gp(xs, ys, noise, xs_star, l_init, sigma_f_init, l_noise_init, sigma_f_noise_init, gp2_noise, num_iters, sample_size):
    """
    Fit a heteroscedastic GP to data (xs, ys) and compute the negative log predictive density at new input locations
    xs_star.

    :param xs: input locations N x D
    :param ys: target labels
    :param noise: fixed noise level or noise function
    :param xs_star: test input locations
    :param l_init: lengthscale(s) to initialise the optimiser
    :param sigma_f_init: signal amplitude to initialise the optimiser
    :param l_noise_init: lengthscale(s) to initialise the optimiser for the noise
    :param sigma_f_noise_init: signal amplitude to initialise the optimiser for the noise
    :param gp2_noise: the noise level for the second GP modelling the noise (noise of the noise)
    :param num_iters: number of iterations to run the most likely heteroscedastic GP algorithm.
    :param sample_size: the number of samples for the heteroscedastic GP algorithm.
    :return: The negative log marginal likelihood value and the negative log predictive density at the test input locations.
    """

    dimensionality = xs.shape[1]  # in order to plot only in the 1D input case.
    gp1_hypers = [l_init]*dimensionality + [sigma_f_init]  # we initialise each dimension with the same lengthscale value
    gp2_hypers = [l_noise_init]*dimensionality + [sigma_f_noise_init]  # we initialise each dimensions with the same lengthscale value for gp2 as well.
    bounds = [(0.2, 300)]*len(gp1_hypers)  # we initialise the bounds to be the same in each case

    for i in range(0, num_iters):

        # We fit GP1 to the data

        gp1_res = minimize(nll_fn(xs, ys, noise), gp1_hypers, bounds=bounds, method='L-BFGS-B')

        # We collect the hyperparameters from the optimisation

        gp1_l_opt = np.array(gp1_res.x[:-1]).reshape(-1, 1)
        gp1_sigma_f_opt = gp1_res.x[-1]
        gp1_hypers = list(np.ndarray.flatten(gp1_l_opt)) + [gp1_sigma_f_opt]  # we initialise the optimisation at the next iteration with the optimised hypers

        # We compute the posterior predictive at the test locations

        gp1_pred_mean, gp1_pred_var, _, _ = posterior_predictive(xs, ys, xs_star, noise, gp1_l_opt, gp1_sigma_f_opt, mean_func=zero_mean, kernel=scipy_kernel)

        # We plot the fit on the final iteration.

        f_gp1_plot_posterior = False

        if i == num_iters - 1 and dimensionality == 1:
            f_gp1_plot_posterior = True

        f_gp1_plot_posterior_2d = False

        # Switch designed for the scallop dataset

        if i == num_iters - 1 and dimensionality == 2:
            f_gp1_plot_posterior_2d = True

        if f_gp1_plot_posterior_2d:

            x1_star = np.arange(38.5, 41.0, 0.05)  # hardcoded limits for the scallop dataset.
            x2_star = np.arange(-74.0, -71.0, 0.05) # hardcoded limits for the scallop dataset.
            xs_star_plot = np.array(np.meshgrid(x1_star, x2_star)).T.reshape(-1, 2)  # Where 2 gives the dimensionality

            gp1_plot_pred_mean, gp1_plot_pred_var, _, _ = posterior_predictive(xs, ys, xs_star_plot, noise, gp1_l_opt, gp1_sigma_f_opt, mean_func=zero_mean, kernel=scipy_kernel, full_cov=False)

            gp1_plot_pred_mean = gp1_plot_pred_mean.reshape(len(x1_star), len(x2_star)).T
            gp1_plot_pred_var = gp1_plot_pred_var.reshape(len(x1_star), len(x2_star)).T
            X, Y = np.meshgrid(x1_star, x2_star)

            upper = gp1_plot_pred_mean + 2 * np.sqrt(gp1_plot_pred_var)
            lower = gp1_plot_pred_mean - 2 * np.sqrt(gp1_plot_pred_var)

            fig = plt.figure()
            ax = plt.axes(projection='3d')
            ax.plot_surface(X, Y, gp1_plot_pred_mean)
            #ax.plot_surface(X, Y, upper, color='gray', alpha=0.4)
            #ax.plot_surface(X, Y, lower, color='gray', alpha=0.4)
            ax.scatter(xs[:, 0], xs[:, 1], ys, '+', color='red')
            plt.show()

        if f_gp1_plot_posterior:
            gp1_plot_pred_var = np.diag(gp1_pred_var).reshape(-1, 1)  # Take the diagonal of the covariance matrix for plotting purposes
            gp1_plot_pred_var = gp1_plot_pred_var + noise
            plt.plot(xs, ys, '+', color='green', markersize='12', linewidth='8')
            plt.plot(xs_star, gp1_pred_mean, '-', color='red')
            upper = gp1_pred_mean + 2 * np.sqrt(gp1_plot_pred_var)
            lower = gp1_pred_mean - 2 * np.sqrt(gp1_plot_pred_var)
            upper = upper.reshape(xs_star.shape)
            lower = lower.reshape(xs_star.shape)
            plt.fill_between(xs_star.reshape(len(xs_star),), upper.reshape(len(xs_star),), lower.reshape(len(xs_star),), color='gray', alpha=0.2)
            plt.xlabel('input, x')
            plt.ylabel('f(x)')
            plt.title('GP1 Posterior')
            plt.show()

        # We construct the most likely heteroscedastic GP noise estimator

        sample_matrix = np.zeros((len(ys), sample_size))

        for j in range(0, sample_size):
            sample_matrix[:, j] = np.random.multivariate_normal(gp1_pred_mean.reshape(len(gp1_pred_mean)), gp1_pred_var)

        variance_estimator = (0.5 / sample_size) * np.sum((ys - sample_matrix) ** 2, axis=1) # Equation given in section 4 of Kersting et al. vector of noise for each data point.
        variance_estimator = np.log(variance_estimator)

        # We fit a second GP to the auxiliary dataset z = (xs, variance_estimator)

        gp2_res = minimize(nll_fn(xs, variance_estimator, gp2_noise), gp2_hypers, bounds=bounds, method='L-BFGS-B')

        # We collect the hyperparameters

        gp2_l_opt = np.array(gp2_res.x[:-1]).reshape(-1, 1)
        gp2_sigma_f_opt = gp2_res.x[-1]
        gp2_hypers = list(np.ndarray.flatten(gp2_l_opt)) + [gp2_sigma_f_opt]  # we initialise the optimisation at the next iteration with the optimised hypers

        # we reshape the variance estimator here so that it can be passed into posterior_predictive.

        variance_estimator = variance_estimator.reshape(len(variance_estimator), 1)

        gp2_pred_mean, gp2_pred_var, _, _ = posterior_predictive(xs, variance_estimator, xs_star, gp2_noise, gp2_l_opt, gp2_sigma_f_opt, mean_func=zero_mean, kernel=scipy_kernel)
        gp2_pred_mean = np.exp(gp2_pred_mean)
        noise = np.sqrt(gp2_pred_mean)

        f_gp2_plot_posterior = False

        if f_gp2_plot_posterior:
            gp2_plot_pred_var = np.diag(gp2_pred_var).reshape(-1, 1)  # Take the diagonal of the covariance matrix for plotting purposes
            plt.plot(xs, variance_estimator, '+', color='green', markersize='12', linewidth='8')
            plt.plot(xs_star, np.log(gp2_pred_mean), '-', color='red')
            upper = np.log(gp2_pred_mean) + 2 * np.sqrt(gp2_plot_pred_var)
            lower = np.log(gp2_pred_mean) - 2 * np.sqrt(gp2_plot_pred_var)
            upper = upper.reshape(xs_star.shape[0],)
            lower = lower.reshape(xs_star.shape[0],)
            plt.fill_between(xs_star.reshape(len(xs_star),), upper, lower, color='gray', alpha=0.2)
            plt.xlabel('input, x')
            plt.ylabel('log variance')
            plt.title('GP2 Posterior')
            plt.show()

    return noise, gp2_noise, gp1_l_opt, gp1_sigma_f_opt, gp2_l_opt, gp2_sigma_f_opt, variance_estimator