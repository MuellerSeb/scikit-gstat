"""
Variogram
"""

from skgstat.distance import nd_dist
from skgstat.estimator import matheron, cressie, dowd, genton, minmax, entropy
from skgstat.models import spherical, exponential, gaussian, cubic, stable, matern
import numpy as np
from pandas import DataFrame
import copy
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit


class Variogram(object):
    """

    """
    def __init__(self,
                 coordinates=None,
                 values=None,
                 estimator=matheron,
                 model=spherical,
                 dist_func='euclidean',
                 bin_func='even',
                 normalize=True,
                 fit_method='lm',
                 is_directional=False,
                 azimuth=0,
                 tolerance=45.0,
                 use_nugget=False,
                 maxlag=None,
                 lags=10,
                 verbose=False,
                 harmonize=False
                 ):
        """


        """
        # Set coordinates and values
        self._X = np.asarray(coordinates)
        self._values = None
        self.set_values(values=values)

        # set verbosity
        self.verbose = verbose

        # lags and max lag
        self.lags = lags
        self.maxlag = maxlag

        # set distance calculation function
        self._dist_func = None
        self.set_dist_function(func=dist_func)

        # estimator can be a function or a string
        self._estimator = None
        self.set_estimator(estimator=estimator)

        # model can be a function or a string
        self._model = None
        self.set_model(model=model)

        # the binning settings
        self._bin_func = None
        self._groups = None
        self._bins = None
        self.set_bin_func(bins=bin_func)

        # specify if the lag should be given absolute or relative to the maxlag
        self.normalized = normalize

        # specify if the experimental variogram shall be harmonized
        self.harmonize = harmonize

        # set the fitting method
        self.fit_method = fit_method

        # set directionality
        self.is_directional = is_directional
        self.azimuth = azimuth
        self.tolerance = tolerance

        # set if nugget effect shall be used
        self.use_nugget = use_nugget

        # set attributes to be filled during calculation
        self.cov = None
        self.cof = None

        # distance matrix
        self._dist = None

        # pairwise differences
        self._diff = None

        # do the preprocessing upon initialization
        self.preprocessing()

    @property
    def values(self):
        return self._values

    @values.setter
    def values(self, values):
        self.set_values(values=values)

    def set_values(self, values):
        assert len(values) == len(self._X)

        # set new values
        self._values = np.asarray(values)

        recalulate the pairwise differences
        self._calc_diff()

    @property
    def bin_func(self):
        return self._bin_func

    @bin_func.setter
    def bin_func(self, bin_func):
        self.set_bin_func(bin_func=bin_func)

    def set_bin_func(self, bin_func):
        # reset groups and bins
        self._groups = None
        self._bins = None

        if bin_func.lower() == 'even':
            pass
        elif bin_func.lower() == 'uniform':
            pass
        else:
            raise ValueError('%s binning method is not known' % bin_func)

    @property
    def estimator(self):
        return self._estimator

    @estimator.setter
    def estimator(self, value):
        self.set_estimator(estimator=value)

    def set_estimator(self, estimator):
        """
        Set estimator as the new variogram estimator.

        """
        if isinstance(estimator, str):
            if estimator.lower() == 'matheron':
                self._estimator = matheron
            elif estimator.lower() == 'cressie':
                self._estimator = cressie
            elif estimator.lower() == 'dowd':
                self._estimator = dowd
            elif estimator.lower() == 'genton':
                self._estimator = genton
            elif estimator.lower() == 'minmax':
                self._estimator = minmax
            elif estimator.lower() == 'entropy' or estimator.lower() == 'h':
                self._estimator = entropy
            else:
                raise ValueError('Variogram estimator %s is not understood, please provide the function.' % estimator)
        else:
            self._estimator = estimator

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self.set_model(model=value)

    def set_model(self, model):
        """
        Set model as the new theoretical variogram function.

        """
        if isinstance(model, str):
            if model.lower() == 'spherical':
                self._model = spherical
            elif model.lower() == 'exponential':
                self._model = exponential
            elif model.lower() == 'gaussian':
                self._model = gaussian
            elif model.lower() == 'cubic':
                self._model = cubic
            elif model.lower() == 'stable':
                self._model = stable
            elif model.lower() == 'matern':
                self._model = matern
            else:
                raise ValueError('The theoretical Variogram function %s is not understood, '
                                 'please provide the function' % model)
        else:
            self._model = model

    @property
    def dist_function(self):
        return self._dist_func

    @dist_function.setter
    def dist_function(self, func):
        self.set_dist_function(func=func)

    def set_dist_function(self, func):
        """

        Parameters
        ----------
        func

        Returns
        -------

        """
        # reset the distances
        self._dist = None

        if isinstance(func, str):
            if func.lower() == 'euclidean':
                self._dist_func = nd_dist
            else:
                raise ValueError('%s is not a known distance function' % func)
        elif callable(func):
            self._dist_func = func
        else:
            raise ValueError('Input not supported. Pass a string or callable.')

    @property
    def distances(self):
        if self._dist is None:
            self._calc_distances()
        return self._dist

    @distances.setter
    def distances(self, dist_array):
        self._dist = dist_array

    @property
    def maxlag(self):
        return self._maxlag

    @maxlag.setter
    def maxlag(self, value):
        # set new maxlag
        if value is None:
            self._maxlag = None
        elif value < 1:
            self._maxlag = value * np.max(self.dm)
        else:
            self._maxlag = value

    def preprocessing(self, force=False):
        """Preprocessing function

        Prepares all input data for the fit and transform functions. Namely,
        the distances are calculated and the value differences. Then the
        binning is set up and bin edges are calculated. If any of the listed
        subsets are already prepared, their processing is skipped. This
        behaviour can be changed by the force parameter. This will cause a
        clean preprocessing.

        Parameters
        ----------
        force : bool
            If set to True, all preprocessing data sets will be deleted. Use
            it in case you need a clean preprocessing.

        Returns
        -------
        void

        """
        if force:
            self._dist = None
            self._diff = None
            self._bins = None
            self._groups = None

        # call the _calc functions
        self._calc_distances()
        self._calc_diff()
        self._calc_groups()


    def fit(self, x, y):
        """
        REWRITE

        """
        # if last bin is set, delete it
        if hasattr(self, 'last_bin'):
            del self.last_bin

        # remove nans
        _x = x[~np.isnan(y)]
        _y = y[~np.isnan(y)]

        if self.fit_method == 'lm':
            bounds = (0, self.__get_fit_bounds(x, y))
            return curve_fit(self._model, _x, _y, p0=bounds[1], bounds=bounds)

        else:
            raise ValueError('The fit method {} is not understood. Use either \'lm\' (least squares) or \'pec\' (point exclusion cost).'.format(self.fit_method))

    def _calc_distances(self):
        self._dist = self._dist_func(self._X)

    def _calc_diff(self):
        """Calculates the pairwise differences

        Returns
        -------

        """
        v = self.values
        l = len(v)
        self._diff = np.zeros(int((l**2 - l) / 2))

        for t,k in zip(self.__vdiff_indexer(), range(len(self._diff))):
            self._diff[k] = np.abs(v[t[0]], v[t[1]])

    def __vdiff_indexer(self):
        """Pairwise indexer

        Returns an iterator over the values or coordinates in squareform
        coordinates. The iterable will be of type tuple.

        Returns
        -------
        iterable

        """
        l = len(self.values)

        for i in range(l):
            for j in range(l):
                if i > j:
                    yield i,j

    def _calc_groups(self):
        """Calculate the lag class mask array

        Returns
        -------

        """

    def clone(self):
        """
        Wrapper for copy.deepcopy function of self.
        """
        return copy.deepcopy(self)

    @property
    def experimental(self):
        """
        Return the experimental variogram.
        If :param harmonize: is True, it will return self.isotonic, instead of self.experimental.

        :return: np.array, the isotonic or non-isotonic experimental varigram
        """
        if self.harmonize:
            return self.isotonic
        else:
            return self._experimental

    @property
    def _experimental(self):
        """
        :return: experimental variogram as a numpy.ndarray.

        """
        raise NotImplementedError
        # group the values to bins and apply the estimator
        _g = self.grouped_pairs

        # apply
        return np.array(self._estimator(_g))

    @property
    def isotonic(self):
        """
        Return the isotonic harmonized experimental variogram.
        This means, the experimental variogram is monotonic after harmonization.

        The harmonization is done using PAVA algorithm:

        Barlow, R., D. Bartholomew, et al. (1972): Statistical Interference Under Order Restrictions.
            John Wiley and Sons, New York.
        Hiterding, A. (2003): Entwicklung hybrider Interpolationsverfahren für den automatisierten Betrieb am
            Beispiel meteorologischer Größen. Dissertation, Institut für Geoinformatik, Westphälische
            Wilhelms-Universität Münster, IfGIprints, Münster. ISBN: 3-936616-12-4

        TODO: solve the import

        :return: np.ndarray, monotonized experimental variogram
        """
        # TODO this is imported in the function as sklearn is not a dependency (and should not be for now)
        raise NotImplementedError

        try:
            from sklearn.isotonic import IsotonicRegression
            y = self._experimental
            x = self.bins
            return IsotonicRegression().fit_transform(x,y)
        except ImportError:
            raise NotImplementedError('scikit-learn is not installed, but the isotonic function without sklear dependency is not installed yet.')

    def __get_fit_bounds(self, x, y):
        """
        Return the bounds for parameter space in fitting a variogram model. The bounds are depended on the Model
        that is used

        :return:
        """
        mname = self._model.__name__

        # use range, sill and smoothness parameter
        if mname == 'matern':
            # a is max(x), C0 is max(y) s is limited to 20?
            bounds = [np.nanmax(x), np.nanmax(y), 20.]

        # use range, sill and shape parameter
        elif mname == 'stable':
            # a is max(x), C0 is max(y) s is limited to 2?
            bounds = [np.nanmax(x), np.nanmax(y), 2.]

        # use only sill
        elif mname == 'nugget':
            # a is max(x):
            bounds = [np.nanmax(x)]

        # use range and sill
        else:
            # a is max(x), C0 is max(y)
            bounds = [np.nanmax(x), np.nanmax(y)]

        # if use_nugget is True add the nugget
        if self.use_nugget:
            bounds.append(0.99)

        return bounds

    @property
    def data(self):
        """
        Calculates the experimental Variogram. As the bins are only indexed by a integer, the lag array is caculated
        by cummulative summarizing the bin_widths array. If this bin_widths was not returned by the bm_func, even bin
        widths are created matching the number of bins at the maximum entry in the distance matrix. This will lead to
        calculation errors, in case the bin widths are not even.
        The theoretical variogram function is fitted to the experimental values at given lags
        and the theoretical function is calculated for all increments and returned.

        :return:
        """
        # calculate the experimental variogram
        # this might raise an exception if the bm is not present yet
        _exp = self.experimental
        _bin = self.bins

        # use relative or absolute bins
        if self.normalized:
            _bin /= np.nanmax(_bin)     # normalize X
            _exp /= np.nanmax(_exp)     # normalize Y
            x = np.linspace(0, 1, 100)  # use 100 increments
        else:
            x = np.linspace(0, np.float64(np.nanmax(_bin)), 100)

        # fit
        self.cof, self.cov = self.fit(_bin, _exp)

        return x, self._model(x, *self.cof)

    @property
    def residuals(self):
        """

        :return:
        """
        # get the deviations
        experimental, model = self.__model_deviations()

        # calculate the residuals
        return np.fromiter(map(lambda x, y: x - y, model, experimental), np.float)

    @property
    def mean_residual(self):
        """

        :return:
        """
        return np.nanmean(np.fromiter(map(np.abs, self.residuals), np.float))

    @property
    def RMSE(self):
        # get the deviations
        experimental, model = self.__model_deviations()

        # get the sum of squares
        rsum = np.nansum(np.fromiter(map(lambda x, y: (x - y)**2, experimental, model), np.float))

        return np.sqrt(rsum / len(model))

    @property
    def NRMSE(self):
        return self.RMSE / np.nanmean(self.experimental)

    @property
    def NRMSE_r(self):
        return self.RMSE / (np.nanmax(self.experimental) - np.nanmean(self.experimental))

    @property
    def r(self):
        """
        Pearson correlation of the fitted Variogram

        :return:
        """
        # get the experimental and theoretical variogram and cacluate means
        experimental, model = self.__model_deviations()
        mx = np.nanmean(experimental)
        my = np.nanmean(model)

        # claculate the single pearson correlation terms
        term1 = np.nansum(np.fromiter(map(lambda x, y: (x-mx) * (y-my), experimental, model), np.float))

        t2x = np.nansum(np.fromiter(map(lambda x: (x-mx)**2, experimental), np.float))
        t2y = np.nansum(np.fromiter(map(lambda y: (y-my)**2, model), np.float))

        return term1 / (np.sqrt(t2x * t2y))

    @property
    def NS(self):
        """
        Nash Sutcliffe efficiency of the fitted Variogram

        :return:
        """
        experimental, model = self.__model_deviations()
        mx = np.nanmean(experimental)

        # calculate the single nash-sutcliffe terms
        term1 = np.nansum(np.fromiter(map(lambda x, y: (x - y)**2, experimental, model), np.float))
        term2 = np.nansum(np.fromiter(map(lambda x: (x - mx)**2, experimental), np.float))

        return 1 - (term1 / term2)

    def __model_deviations(self):
        """
        These model deviations can be used to calculate different model quality parameters like residuals, RMSE.
        :return:
        """
        # get the experimental values and their bin bounds
        _exp = self.experimental
        _bin = self.bins

        # get the model parameters
        param = self.describe()
        if 'error' in param:
            raise RuntimeError('The Variogram cannot be applied properly. First, calculate the variogram.')

        # calculate the model values at bin bounds
        _model = self._model(_bin, *self.cof)

        return _exp, _model

    def describe(self):
        """
        Return a dictionary of the Variogram parameters

        :return:
        """
        try:
            if self.normalized:
                maxlag = np.nanmax(self.bins)
                maxvar = np.nanmax(self.experimental)
            else:
                maxlag = 1
                maxvar = 1
            index, data = self.data
            cof = self.cof
        except:
            return dict(name=self._model.__name__, estimator = self._estimator.__name__, error='Variogram not calculated.')
        rdict = dict(
            name=self._model.__name__,
            estimator=self._estimator.__name__,
            range=cof[0] * maxlag,
            sill=cof[1] * maxvar,
            nugget=cof[-1] * maxvar if self.use_nugget else 0
        )

        # handle s parameters
        if self._model.__name__ == 'matern':
            rdict['smoothness'] = cof[2]
        elif self._model.__name__ == 'stable':
            rdict['shape'] = cof[2]

        return rdict

    @property
    def parameters(self):
        """
        Extract just the variogram parameters range, sill and nugget from the self.describe return

        :return:
        """
        d = self.describe()
        if 'error' in d:
            return [None, None, None]
        elif self._model.__name__ == 'matern':
            return list([d['range'], d['sill'], d['smoothness'], d['nugget']])
        elif self._model.__name__ == 'stable':
            return list([d['range'], d['sill'], d['shape'], d['nugget']])
        elif self._model.__name__ == 'nugget':
            return list([d['nugget']])
        else:
            return list([d['range'], d['sill'], d['nugget']])

    @property
    def hist(self):
        """
        Return a histogram for the present bins in the Variogram. The bin matrix bm will be unstacked and counted.
        Variogram.bins, Variogram.hist could be used to produce a properly labeled histogram.

        :return:
        """
        # get the grouped pairs
        _g = self.grouped_pairs
        return np.array([len(_) / 2 for _ in _g])

    def to_DataFrame(self):
        """
        Return the result of the theoretical Variogram as a pandas.DataFrame. The lag will index the semivariance
        values.

        :return:
        """
        raise NotImplementedError
        index, data = self.data

        # translate the normalized lag to real lag
        maxlag = np.nanmax(self.bins)
        maxvar = np.nanmax(self.experimental)

        return DataFrame({'lag': index * maxlag, self._model.__name__: data * maxvar}).copy()

    def plot(self, axes=None, grid=True, show=True, cof=None):
        """
        Plot the variogram, including the experimental and theoretical variogram. By default, the experimental data
        will be represented by blue points and the theoretical model by a green line.

        TODO: REWORK this

        :return:
        """
        raise NotImplementedError
        try:
            _bin, _exp = self.bins, self.experimental
            if cof is None:
                x, data = self.data
            else:
                x = np.linspace(0, 1, 100) if self.normalized else np.linspace(0, np.nanmax(_bin), 100)
                data = self._model(x, *cof)
            _hist = self.hist
        except Exception as e:
            raise RuntimeError('A chart could not be drawn, as the input data is not complete. Please calculate the Variogram first.\nDetailed message: %s.' % str(e))

        # handle the relative experimental variogram
        if self.normalized:
            _bin /= np.nanmax(_bin)
            _exp /= np.nanmax(_exp)

        # do the plotting
        if axes is None:
            fig = plt.figure()
            ax1 = plt.subplot2grid((5, 1), (1, 0), rowspan=4)
            ax2 = plt.subplot2grid((5, 1), (0, 0), sharex=ax1)
            fig.subplots_adjust(hspace=0)
        else:
            ax1, ax2 = axes
            fig = ax1.get_figure()

        # calc histgram bar width
        # bar use 70% of the axis, w is the total width divided by amount of bins in the histogram
        w = (np.max(_bin) * 0.7) / len(_hist)

        # plot Variograms

        # if last_bin is set, plot only considered bins in blue, excluded in red
        ax1.plot(_bin, _exp, '.b')
        ax1.plot(x, data, '-g')

        if hasattr(self, 'last_bin'):
            ax1.plot(_bin[self.last_bin:], _exp[self.last_bin:], '.r')


        # plot histogram
        ax2.bar(_bin, _hist, width=w, align='center')
        # adjust
        plt.setp(ax2.axes.get_xticklabels(), visible=False)
        ax2.axes.set_yticks(ax2.axes.get_yticks()[1:])

        # ax limits
        if self.normalized:
            ax1.set_xlim([0, 1.05])
            ax1.set_ylim([0, 1.05])

        if grid:
            ax1.vlines(_bin, *ax1.axes.get_ybound(), colors=(.85, .85, .85), linestyles='dashed')
            ax2.vlines(_bin, *ax2.axes.get_ybound(), colors=(.85, .85, .85), linestyles='dashed')

        # annotation
        ax1.axes.set_ylabel('semivariance (%s)' % self._estimator.__name__)
        ax1.axes.set_xlabel('Lag (-)')
        ax2.axes.set_ylabel('N')

        # show the figure
        if show:
            fig.show()

        return fig

    def scattergram(self, ax=None, plot=True):
        """
        Plot a scattergram, which is a scatter plot of

        :return:
        """
        raise NotImplementedError
        # calculate population mean
        _mean = np.mean(self.values1D)

        # group the values to bins
        gbm = self.grouped_pairs

        # create the tail and head arrays
        tail, head = list(), list()

        # order the point pairs to tail and head
        for grp in gbm:
            # the even values are z(x) and odd values are z(x+h)
            for i in range(0, len(grp) - 1, 2):
                tail.append(_mean - grp[i])
                head.append(_mean - grp[i + 1])

        # if no plot is questioned, return tail and head arrays
        if not plot:
            return tail, head

        # else plot in either given Ax object or create a new one
        if ax is None:
            fig, ax = plt.subplots(1, 1)
        else:
            fig = ax.get_figure()

        # plot
        ax.plot(tail, head, '.k')

        # show the figure
        fig.show()

        return fig

    def location_trend(self, axes=None):
        """
        Plot the values over each dimension in the coordinates as a scatter plot.
        These plots can be used to identify a correlation between the value of an observation
        and its location. If this is the case, it would violate the fundamental geostatistical
        assumption, that a oberservation is independed of its observation

        :param axes: list of `matplotlib.AxesSubplots`. The len has to match the dimensionality
                        of the coordiantes.

        :return:
        """
        N = len(self._X[0])
        if axes is None:
            # derive the needed amount of col and row
            nrow = int(round(np.sqrt(N)))
            ncol = int(np.ceil(N / nrow))
            fig, axes = plt.subplots(nrow, ncol, figsize=(ncol * 6 ,nrow * 6))
        else:
            if not len(axes) == N:
                raise ValueError('The amount of passed axes does not fit the coordinate dimensionality of %d' % N)
            fig = axes[0].get_figure()

        for i in range(N):
            axes.flatten()[i].plot([_[i] for _ in self._X], self.values, '.r')
            axes.flatten()[i].set_xlabel('%d-dimension' % (i + 1))
            axes.flatten()[i].set_ylabel('value')

        # plot the figure and return it
        plt.tight_layout()
        fig.show()

        return fig

    def __repr__(self):
        """
        Textual representation of this Variogram instance.

        :return:
        """
        try:
            _name = self._model.__name__
            _b = int(len(self.bins))
        except:
            return "< abstract Variogram >"
        return "< %s Semivariogram fitted to %d bins >" % (_name, _b)

    def __str__(self):
        """
        Descriptive respresentation of this Variogram instance that shall give the main variogram
        parameters in a print statement.

        :return:
        """
        par = self.describe()

        _sill = np.NaN if 'error' in par else par['sill']
        _range = np.NaN if 'error' in par else par['range']
        _nugget = np.NaN if 'error' in par else par['nugget']

        s = "{0} Variogram\n".format(par['name'])
        s+= "-" * (len(s) - 1) + "\n"
        s+= "Estimator:  {0}\nRange:      {1:.2f}\nSill:       {2:.2f}\nNugget:     {3:.2f}\n".format(par['estimator'], _range, _sill, _nugget)

        return s
