import abc
import collections
import functools
import operator

from ... import proba
from ... import utils


def decimal_range(start, stop, num):
    """

    Example:

        >>> for x in decimal_range(1, 3, 5):
        ...     print(x)
        1
        1.5
        2.0
        2.5
        3.0

    """
    step = (stop - start) / (num - 1)

    for _ in range(num):
        yield start
        start += step


class Op(collections.namedtuple('Op', 'symbol operator')):

    def __call__(self, a, b):
        return self.operator(a, b)

    def __repr__(self):
        return self.symbol


LT = Op('<', operator.lt)
EQ = Op('=', operator.eq)


class SplitEnum(abc.ABC):

    @abc.abstractmethod
    def update(self, x, y):
        """Updates the sufficient statistics used for evaluting splits."""

    @abc.abstractmethod
    def enumerate_splits(self):
        """Yields candidate split points and associated operators."""


class HistSplitEnum(SplitEnum):
    """Split enumerator for classification and numerical attributes."""

    def __init__(self, n_bins, n_splits):
        self.P_xy = collections.defaultdict(functools.partial(utils.Histogram, max_bins=n_bins))
        self.n_splits = n_splits

    def update(self, x, y):
        """

        Parameters:
            x (float)
            y (base.Label)

        """
        self.P_xy[y].update(x)
        return self

    def enumerate_splits(self, target_dist):
        """

        Parameters:
            target_dist (proba.Multinomial)

        """

        low = min(h[0].right for h in self.P_xy.values())
        high = min(h[-1].right for h in self.P_xy.values())

        # If only one single value has been observed, then no split can be proposed
        if low >= high:
            return
            yield

        thresholds = list(decimal_range(start=low, stop=high, num=self.n_splits))
        cdfs = {y: hist.iter_cdf(thresholds) for y, hist in self.P_xy.items()}

        for at in thresholds:

            l_dist = {}
            r_dist = {}

            for y in target_dist:
                p_xy = next(cdfs[y]) if y in cdfs else 0.  # P(x < t | y)
                p_y = target_dist.pmf(y)  # P(y)
                l_dist[y] = target_dist.n_samples * p_y * p_xy  # P(y | x < t)
                r_dist[y] = target_dist.n_samples * p_y * (1 - p_xy)  # P(y | x >= t)

            l_dist = proba.Multinomial(l_dist)
            r_dist = proba.Multinomial(r_dist)

            yield LT, at, l_dist, r_dist


class CategoricalSplitEnum(SplitEnum):
    """Split enumerator for classification and categorical attributes."""

    def __init__(self):
        self.P_xy = collections.defaultdict(proba.Multinomial)

    def update(self, x, y):
        """

        Parameters:
            x (str)
            y (base.Label)

        """
        self.P_xy[y].update(x)
        return self

    def enumerate_splits(self, target_dist):
        """

        Parameters:
            target_dist (proba.Multinomial)

        """

        categories = set(*(p_x.keys() for p_x in self.P_xy.values()))

        # There has to be at least two categories for a split to be possible
        if len(categories) < 2:
            return
            yield

        for cat in categories:

            l_dist = {}
            r_dist = {}

            for y in target_dist:
                p_xy = self.P_xy[y].pmf(cat)  # P(cat | y)
                p_y = target_dist.pmf(y)  # P(y)
                l_dist[y] = target_dist.n_samples * p_y * p_xy  # P(y | cat)
                r_dist[y] = target_dist.n_samples * p_y * (1. - p_xy)  # P(y | !cat)

            l_dist = proba.Multinomial(l_dist)
            r_dist = proba.Multinomial(r_dist)

            yield EQ, cat, l_dist, r_dist
