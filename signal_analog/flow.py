# -*- coding: utf-8 -*-

"""This module provides bindings for the SignalFx SignalFlow DSL."""

from numbers import Number

from six import string_types

import signal_analog.util as util
from signal_analog.combinators import NAryCombinator
from signal_analog.errors import ProgramDoesNotPublishTimeseriesError

# Py 2/3 compatability hack to force `filter` to always return an iterator
try:
    from itertools import ifilter
    filter = ifilter
except ImportError:
    pass


class Program(object):
    """Encapsulation of a SignalFlow program."""

    def __init__(self, *statements):
        """Initialize a new program, optionally with statements.

        Raises:
            ValueError: when any provided statement is found to not be a valid
                        statement. See __valid_statement__ for more detail.
        """
        self.statements = []
        for stmt in statements:
            self.__valid_statement__(stmt)
            self.statements.append(stmt)

    def __str__(self):
        return '\n'.join(map(str, self.statements))

    def validate(self, *validations):
        """Validate this Program.

        If no validations are provided this Program will validate against all
        validation functions from self.DEFAULT_VALIDATIONS.

        A validation function is one that inspects the given Programs
        statements and returns nothing if verified, an appropriate Exception
        otherwise.

        Arguments:
            validations: if provided, override the default validations for this
                         program.

        Returns:
            An appropriate Exception if invalid, None otherwise.
        """
        defaults = [
            Program.validate_publish_statements
        ]

        valid_fns = validations if validations else defaults

        for validation in valid_fns:
            validation(self.statements)

    def __valid_statement__(self, stmt):
        """Type check the provided statement."""
        if not stmt or not issubclass(stmt.__class__, Function):
            msg = "Attempted to build a program with something other than " +\
                   "SignalFlow statements. Received '{0}' but expected a " +\
                   "{1}"
            raise ValueError(msg.format(
                stmt.__class__.__name__, Function.__name__))

    def add_statements(self, *statements):
        """Add a statement to this program.

        Arguments:
            statement: the statement to add

        Raises:
            ValueError: when any provided statement is found to not be a valid
                        statement. See __valid_statement__ for more detail.

        Returns:
            None
        """
        for stmt in statements:
            self.__valid_statement__(stmt)
            self.statements.append(stmt)


    def find_label(self, label):
        """Find a statement in this program with the given label.

        Note that any program that doesn't call `publish` will be ignored.

        Arguments:
            label: the label to search for.

        Returns:
            The first match for `label` in this program's statements. None if
            a match cannot be found.
        """
        def label_predicate(x):
            # Search the call stack for a publish call
            for call in x.call_stack:
                if isinstance(call, Publish):
                    # Check that the label arg is equal to the label we're
                    # searching for.
                    return label == call.args[0].arg

            # If we didn't a publish call let's ignore it.
            return False

        # Only return the first match from the filter iterator.
        return next(filter(label_predicate, self.statements), None)

    @staticmethod
    def validate_publish_statements(statements):
        """Validate that at least 1 statement is published for this Program."""
        def find_publish(statement):

            # Inspect the left hand side of the assignment
            if isinstance(statement, Assign):
                statement = statement.expr

            # We technically shouldn't see naked combinators in a Program
            # object, but out of an abundance of caution...
            if isinstance(statement, NAryCombinator):
                return False

            for call in statement.call_stack:
                if isinstance(call, Publish):
                    return True

        publish_statements = list(filter(find_publish, statements))

        if len(publish_statements) < 1:
            raise ProgramDoesNotPublishTimeseriesError(statements)


class Function(object):

    def __init__(self, name):
        """Base SignalFlow stream function class."""
        self.name = name
        self.args = []
        self.call_stack = []

    def __str__(self):
        str_args = ",".join(map(str, filter(lambda x: x.arg is not None, self.args)))
        if not self.call_stack:
            str_calls = ""
        else:
            str_calls = "." + ".".join(map(str, self.call_stack))

        return "{0}({1}){2}".format(self.name, str_args, str_calls)

    def bottom(self, count=None, percentage=None, by=None):
        """Get the bottom values in the stream."""
        self.call_stack.append(Bottom(count=count, percentage=percentage, by=by))
        return self

    def count(self, by=None, over=None):
        """Counts the number of inputs that have data."""
        self.call_stack.append(Count(by=by, over=over))
        return self

    def delta(self):
        """Calculates the difference between the current value and the
           previous value for each time interval.

        Delta operates independently on each time series."""
        self.call_stack.append(Delta())
        return self

    def dimensions(self, aliases=None, renames=None):
        """The dimensions method duplicates or renames metadata of time series
           in the stream.

           The aliases and renames parameters are optional, but at least one
           must be specified. Any supplied parameter must be a dictionary of
           strings to strings.  The keys of the dictionaries specify the names
           of the new metadata dimensions.  The values of the dictionaries
           specify the corresponding names of existing metadata dimensions or
           custom properties from which the new dimensions are derived.

           The difference between aliases and renames is that aliases introduce
           new dimensions while leaving the existing dimensions as is, whereas
           renames replace existing dimensions.

           The return value is a data stream whose time series have altered
           metadata dimensions

        Arguments:
            aliases: dictionary of strings of strings
            renames: dictionary of strings of strings
        """
        self.call_stack.append(Dimensions(aliases=aliases, renames=renames))
        return self

    def mean(self, by=None, over=None):
        """Find the mean on a stream."""
        self.call_stack.append(Mean(by=by, over=over))
        return self

    def mean_plus_stddev(self, by=None, over=None):
        """Calculates the mean + n standard deviations."""
        self.call_stack.append(Mean_plus_stddev(by=by, over=over))
        return self

    def median(self, by=None, over=None):
        """Find the median on a stream."""
        self.call_stack.append(Median(by=by, over=over))
        return self

    def min(self, by=None, over=None):
        """Find the minimum value on a stream."""
        self.call_stack.append(Min(by=by, over=over))
        return self

    def max(self, by=None, over=None):
        """Find the maximum value on a stream."""
        self.call_stack.append(Max(by=by, over=over))
        return self

    def percentile(self, percentage, by=None, over=None):
        """Calculates the n-th percentile of inputs in the stream."""
        self.call_stack.append(Percentile(percentage, by=by, over=over))
        return self

    def random(self, count, by=None, over=None):
        """Get random values in the stream by count or percentage."""
        self.call_stack.append(Random(count, by=by, over=over))
        return self

    def sample_stddev(self, by=None, over=None):
        """Calculates the sample standard deviation of inputs in the stream."""
        self.call_stack.append(Sample_stddev(by=by, over=over))
        return self

    def sample_variance(self, by=None, over=None):
        """Calculates the sample variance of inputs in the stream."""
        self.call_stack.append(Sample_variance(by=by, over=over))
        return self

    def size(self, by=None, over=None):
        """Counts the number of inputs in the stream."""
        self.call_stack.append(Size(by=by, over=over))
        return self

    def stddev(self, by=None, over=None):
        """Calculates the standard deviation of inputs in the stream."""
        self.call_stack.append(Stddev(by=by, over=over))
        return self

    def sum(self, by=None, over=None):
        """Find the sum on a stream."""
        self.call_stack.append(Sum(by=by, over=over))
        return self

    def top(self, count=None, percentage=None, by=None):
        """Get the top values in the stream."""
        self.call_stack.append(Top(count=count, percentage=percentage, by=by))
        return self

    def variance(self, by=None, over=None):
        """Calculates the variance of inputs in the stream."""
        self.call_stack.append(Variance(by=by, over=over))
        return self

    def integrate(self, by=None, over=None):
        """Multiplies the values of each input time series by the
           resolution (in seconds) of the computation."""
        self.call_stack.append(Integrate(by=by, over=over))
        return self

    def publish(self, label=None, enable=None):
        """Publish the output of a stream so that it is visible outside of a
           computation."""
        self.call_stack.append(Publish(label=label, enable=enable))
        return self

    def timeshift(self, offset):
        """Timeshift the datapoints for a stream, offset by a specified time
           period e.g. 1 week (1w), to enable comparison of time series with
           its own past behavior."""
        self.call_stack.append(Timeshift(offset))
        return self

    def ewma(self, alpha=None, over=None):
        """Calculates the exponentially weighted moving average of the stream.
        """
        self.call_stack.append(Ewma(alpha, over=over))
        return self

    def abs(self):
        """Apply absolute value to data in the stream."""
        self.call_stack.append(Abs())
        return self

    def ceil(self):
        """Apply the ceil() function to data in the stream."""
        self.call_stack.append(Ceil())
        return self

    def floor(self):
        """Apply floor() to data in the stream."""
        self.call_stack.append(Floor())
        return self

    def log(self):
        """Apply the natural log function to data in the stream."""
        self.call_stack.append(Log())
        return self

    def log10(self):
        """Apply the logarithm(base 10) function to data in the stream."""
        self.call_stack.append(Log10())
        return self

    def pow(self, exponent):
        """ - return (stream data)"""
        self.call_stack.append(Pow(exponent))
        return self

    def pow(self, base=None):
        """ - return base"""
        self.call_stack.append(Pow(base=base))
        return self

    def scale(self, multiplier):
        """Scale data in the stream by a multiplier."""
        self.call_stack.append(Scale(multiplier))
        return self

    def sqrt(self):
        """Apply a square root to data in the stream."""
        self.call_stack.append(Sqrt())
        return self

    def above(self, limit, inclusive=None, clamp=None):
        """Only pass through data in the stream that is above a particular
           value, or clamp data above a value to that value.
        """
        self.call_stack.append(Above(limit, inclusive=inclusive, clamp=clamp))
        return self

    def below(self, limit, inclusive=None, clamp=None):
        """Only pass through data in the stream that is below a particular
           value, or clamp data below a value to that value.
        """
        self.call_stack.append(Below(limit, inclusive=inclusive, clamp=clamp))
        return self

    def between(self, low_limit, high_limit,
                low_inclusive=None, high_inclusive=None, clamp=None):
        """Only pass through data in the stream that is between two particular
           values or replace data that is not between two particular values
           with the limit that they are closest to.
        """
        self.call_stack.append(Between(
            low_limit, high_limit,
            low_inclusive=low_inclusive,
            high_inclusive=high_inclusive,
            clamp=clamp))
        return self

    def equals(self, value, replacement=None):
        """Only pass through data in the stream that is equal to a particular
           value or replace data that is not equal to a particular value with
           another value.
        """
        self.call_stack.append(Equals(value, replacement=replacement))
        return self

    def not_between(self, low_limit, high_limit,
                    low_inclusive=None, high_inclusive=None):
        """Only pass through data in the stream that is not between two
           particular values.
        """
        self.call_stack.append(Not_between(
            low_limit, high_limit,
            low_inclusive=low_inclusive, high_inclusive=high_inclusive))
        return self

    def not_equals(self, value, replacement=None):
        """Only pass through data in the stream that is not equal to a
           particular value or replace data that is equal to a particular
           value with another value.
        """
        self.call_stack.append(Not_equals(value, replacement=replacement))
        return self

    def promote(self, *properties):
        """Promotes a metadata property to a dimension."""
        self.call_stack.append(Promote(*properties))
        return self

    def fill(self, value=None, duration=None):
        """Fills in missing values for time series in a stream. See
        https://developers.signalfx.com/reference#fill-stream-method
        """
        self.call_stack.append(Fill(value, duration))
        return self
    
    def integrate(self):
        """Multiplies the values of each input time series by the resolution (in seconds) of the computation.
        See https://developers.signalfx.com/reference#integrate-method
        """
        self.call_stack.append(Integrate())
        return self
    
    def kpss(self, over=None, mode='level'):
        """Calculates the Kwiatkowski–Phillips–Schmidt–Shin (KPSS) statistic on the specified time window of the stream
        see https://developers.signalfx.com/reference#kpss-stream-method
        """
        self.call_stack.append(Kpss(over, mode))
        return self
    
    def rateofchange(self):
        """Calculates the difference between the current value and the previous value for each time interval
        See https://developers.signalfx.com/reference#rateofchange-method
        """
        self.call_stack.append(RateOfChange())
        return self

        
        


class StreamMethod(object):

    def __init__(self, name):
        """Base SignalFlow stream method class."""
        if not name:
            raise Exception("Name cannot be None.")
        self.name = name
        self.args = []

    def __str__(self):
        str_args = ",".join(map(str, filter(lambda x: x.arg is not None, self.args)))
        return "{0}({1})".format(self.name, str_args)


class Arg(object):

    def __init__(self, arg):
        if not arg:
            raise Exception("Arg cannot be None.")
        self.arg = arg

    def __str__(self):
        return str(self.arg)

class StrArg(object):

    def __init__(self, arg):
        if not arg:
            raise Exception("Arg cannot be None.")
        self.arg = arg

    def __str__(self):
        if isinstance(self.arg, Number):
            return str(self.arg)
        else:
            return "\"" + str(self.arg) + "\""


class KWArg(object):

    def __init__(self, keyword, arg):
        if not keyword:
            raise Exception("Keyword cannot be None.")
        self.keyword = keyword
        self.arg = arg

    def __str__(self):
        str_arg = self.arg
        if isinstance(self.arg, string_types):
            str_arg = "\"" + self.arg + "\""
        elif isinstance(self.arg, Number):
            str_arg = str(self.arg)
        return "%s=%s" % (self.keyword, str_arg)

    def __eq__(self, other):
        return self.arg == other.arg and self.arg == other.arg

    def __repr__(self):
        return self.__str__()

class VarStrArg(object):

    def __init__(self, args):
        self.arg = args

    def __str__(self):
        return ",".join(map(lambda x: str(StrArg(x)), self.arg))


class Data(Function):

    def __init__(self, metric, filter=None,
                 rollup=None, extrapolation=None, maxExtrapolations=None):
        """The data() function is used to create a stream."""
        super(Data, self).__init__("data")
        self.args = [
            StrArg(metric),
            KWArg("filter", filter),
            KWArg("rollup", rollup),
            KWArg("extrapolation", extrapolation),
            KWArg("maxExtrapolations", maxExtrapolations)
        ]


class Filter(Function):

    def __init__(self, parameter_name, query, *args):
        """Creates a _filter_ object."""
        super(Filter, self).__init__("filter")
        self.args = [StrArg(parameter_name), StrArg(query), VarStrArg(args)]


class Const(Function):

    def __init__(self, value, key, timeseries):
        """The const() function is used to create a stream of constant-value
           timeseries.
        """
        super(Const, self).__init__("const")
        self.args = [StrArg(value), StrArg(key), StrArg(timeseries)]


class Graphite(Function):

    def __init__(self, metric, rollup=None, extrapolation=None,
                 maxExtrapolations=None, **kwargs):
        """The graphite() function is used to create a stream interpreting the
           metric query as a series of period separated dimensions.
        """
        super(Graphite, self).__init__("graphite")
        self.args = [
            StrArg(metric),
            KWArg("rollup", rollup),
            KWArg("extrapolation", extrapolation),
            KWArg("maxExtrapolations", maxExtrapolations),
            StrArg("foo")
        ]


class Newrelic(Function):

    def __init__(self, metric, filter=None, rollup=None,
                 extrapolation=None, maxExtrapolations=None, **kwargs):
        """The newrelic() function is used to create a stream interpreting the
           metric query as a series of slash separated dimensions.
        """
        super(Newrelic, self).__init__("newrelic")
        self.args = [
            StrArg(metric),
            KWArg("filter", filter),
            KWArg("rollup", rollup),
            KWArg("extrapolation", extrapolation),
            KWArg("maxExtrapolations", maxExtrapolations),
            StrArg("foo")
        ]


class Union(Function):

    def __init__(self):
        """The union function merges multiple time series streams into a single
           time series stream.
        """
        super(Union, self).__init__("union")
        self.args = []


class Detect(Function):

    def __init__(self, on, off=None, mode=None):
        """Creates a  object.

        A 'detect' object is used to create events when a  condition is met
        and when it clears. These events can be used to notify people of when
        the conditions within the detect block are met. In order to actually
        publish the events the  must be invoked on a stream.
        """
        super(Detect, self).__init__("detect")
        self.args = [Arg(on), KWArg("off", off), KWArg("mode", mode)]


class Op(Function):
    """Op combines two streams using mathematical operators and function calls
    into a SignalFlow Formula that can be used in a Chart of Detector.

    A Formula in SignalFlow requires operations such as *, /, +, - and allows function
    calls such as .sum(), .publish(), etc
    """
    def __init__(self, stmt):
        super(Op, self).__init__("")
        self.args = [Arg(stmt)]


class When(Function):

    def __init__(self, predicate, lasting=None, at_least=None):
        """Creates a  object for use in  functions."""
        super(When, self).__init__("when")
        self.args = [Arg(predicate), KWArg(
            "lasting", lasting), KWArg("at_least", at_least)]


class Lasting(Function):

    def __init__(self, lasting=None, at_least=None):
        """Convenience wrapper for holding both the lasting and optionally the
           at_least parameter to pass to a  function."""
        super(Lasting, self).__init__("lasting")
        self.args = [KWArg("lasting", lasting), KWArg("at_least", at_least)]


class Assign(Function):

    def __init__(self, assignee, expr):
        """Assign the given expression to the assignee

        Arguments:
            assignee: the name to which to assign the expression
            expr: the expression to assign

        Returns:
            An object that can be serialized to SignalFlow
        """

        # Ensure that assignee is valid and is a string
        util.assert_valid(assignee, str)

        # Ensure that expr is valid
        util.assert_valid(expr)

        self.assignee = assignee
        self.expr = expr

    def __str__(self):
        return str(self.assignee) + " = " + str(self.expr)

class AggregationTransformationMixin(object):
    """Mixin providing pre-condition checks for StreamMethods that perform
       both aggregations and transformations.
    """

    def __init__(self):
        pass

    def check_pre_conditions(self):
        # We only want these pre-conditions to be checked if this mixin is
        # used in conjunction with StreamMethod.
        if StreamMethod not in self.__class__.__bases__:
            msg = "AggregationTransformationMixin cannout be used outside" +\
                  "of a StreamMethod. This is likely a library error and" +\
                  "not a user error. Please file a ticket:\n" +\
                  "https://github.com/Nike-inc/signal_analog/issues"
            raise ValueError(msg)

        # A StreamMethod may have positional arguments and by/over kwargs.
        # In such cases we only want to inspect the first two kwargs defined.
        kwargs = filter(lambda x: issubclass(KWArg, x.__class__), self.args)
        (by, over) = map(lambda x: x.arg, kwargs)

        if by and over:
            msg = '{0} cannot define both "by" and "over" at the same time.'
            raise ValueError(msg.format(self.__class__.__name__))


class Bottom(StreamMethod):

    def __init__(self, count=None, percentage=None, by=None):
        """Get the bottom values in the stream."""
        super(Bottom, self).__init__("bottom")
        self.args = [KWArg("by", count), KWArg("percentage", percentage), KWArg("by", by)]


class Count(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Counts the number of inputs that have data."""
        super(Count, self).__init__("count")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Delta(StreamMethod):

    def __init__(self):
        """Calculates the difference between the current value and the previous
           value for each time interval.
        """
        super(Delta, self).__init__("delta")
        self.args = []


class Mean(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Find the mean on a stream."""
        super(Mean, self).__init__("mean")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Mean_plus_stddev(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Calculates the mean + n standard deviations."""
        super(Mean_plus_stddev, self).__init__("mean_plus_stddev")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()

class Median(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Find the median on a stream."""
        super(Median, self).__init__("median")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Min(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Find the minimum value on a stream."""
        super(Min, self).__init__("min")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Max(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Find the maximum value on a stream."""
        super(Max, self).__init__("max")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Percentile(StreamMethod, AggregationTransformationMixin):

    def __init__(self, percentage, by=None, over=None):
        """Calculates the n-th percentile of inputs in the stream."""
        super(Percentile, self).__init__("percentile")
        self.args = [StrArg(percentage), KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Random(StreamMethod, AggregationTransformationMixin):

    def __init__(self, count, by=None, over=None):
        """Get random values in the stream by count or percentage."""
        super(Random, self).__init__("random")
        self.args = [StrArg(count), KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Sample_stddev(StreamMethod):

    def __init__(self, by=None, over=None):
        """Calculates the sample standard deviation of inputs in the stream."""
        super(Sample_stddev, self).__init__("sample_stddev")
        self.args = [KWArg("by", by), KWArg("over", over)]


class Sample_variance(StreamMethod):

    def __init__(self, by=None, over=None):
        """Calculates the sample variance of inputs in the stream."""
        super(Sample_variance, self).__init__("sample_variance")
        self.args = [KWArg("by", by), KWArg("over", over)]


class Size(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Counts the number of inputs in the stream."""
        super(Size, self).__init__("size")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Stddev(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Calculates the standard deviation of inputs in the stream."""
        super(Stddev, self).__init__("stddev")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Sum(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Find the sum on a stream."""
        super(Sum, self).__init__("sum")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Top(StreamMethod):

    def __init__(self, count=None, percentage=None, by=None):
        """Get the top values in the stream."""
        super(Top, self).__init__("top")
        self.args = [KWArg("count", count), KWArg("percentage", percentage), KWArg("by", by)]


class Variance(StreamMethod, AggregationTransformationMixin):

    def __init__(self, by=None, over=None):
        """Calculates the variance of inputs in the stream."""
        super(Variance, self).__init__("variance")
        self.args = [KWArg("by", by), KWArg("over", over)]
        self.check_pre_conditions()


class Integrate(StreamMethod):

    def __init__(self, by=None, over=None):
        """Multiplies the values of each input time series by the resolution
           (in seconds) of the computation.
        """
        super(Integrate, self).__init__("integrate")
        self.args = [KWArg("by", by), KWArg("over", over)]


class Publish(StreamMethod):

    def __init__(self, label=None, enable=None):
        """Publish the output of a stream so that it is visible outside of a
           computation.
        """
        super(Publish, self).__init__("publish")
        self.args = [KWArg("label", label), KWArg("enable", enable)]


class Timeshift(StreamMethod):

    def __init__(self, offset):
        """Timeshift the datapoints for a stream, offset by a specified time
           period e.g. 1 week (1w), to enable comparison of time series with
           its own past behavior.
        """
        super(Timeshift, self).__init__("timeshift")
        self.args = [StrArg(offset)]


class Ewma(StreamMethod):

    def __init__(self, alpha=None, over=None):
        """Calculates the exponentially weighted moving average of the stream.
ewma(alpha)Returns a new  object."""
        super(Ewma, self).__init__("ewma")

        if alpha and over:
            raise ValueError("You may only define alpha or 'over' when calling ewma.")

        self.args = []

        if alpha:
            self.args.append(StrArg(alpha))

        self.args.append(KWArg("over", over))


class Abs(StreamMethod):

    def __init__(self):
        """Apply absolute value to data in the stream.abs()Returns reference to
           the input  object.
        """
        super(Abs, self).__init__("abs")
        self.args = []


class Ceil(StreamMethod):

    def __init__(self):
        """Apply the ceil() function to data in the stream."""
        super(Ceil, self).__init__("ceil")
        self.args = []


class Floor(StreamMethod):

    def __init__(self):
        """Apply floor() to data in the stream."""
        super(Floor, self).__init__("floor")
        self.args = []


class Log(StreamMethod):

    def __init__(self):
        """Apply the natural log function to data in the stream."""
        super(Log, self).__init__("log")
        self.args = []


class Log10(StreamMethod):

    def __init__(self):
        """Apply the logarithm(base 10) function to data in the stream."""
        super(Log10, self).__init__("log10")
        self.args = []


class Pow(StreamMethod):

    def __init__(self, exponent):
        """ - return (stream data)"""
        super(Pow, self).__init__("pow")
        self.args = [StrArg(exponent)]


class Pow(StreamMethod):

    def __init__(self, base=None):
        """ - return base"""
        super(Pow, self).__init__("pow")
        self.args = [KWArg("base", base)]


class Scale(StreamMethod):

    def __init__(self, multiplier):
        """Scale data in the stream by a multiplier."""
        super(Scale, self).__init__("scale")
        self.args = [StrArg(multiplier)]


class Sqrt(StreamMethod):

    def __init__(self):
        """Apply a square root to data in the stream."""
        super(Sqrt, self).__init__("sqrt")
        self.args = []


class Above(StreamMethod):

    def __init__(self, limit, inclusive=None, clamp=None):
        """Only pass through data in the stream that is above a particular
           value, or clamp data above a value to that value.
        """
        super(Above, self).__init__("above")
        self.args = [StrArg(limit), KWArg(
            "inclusive", inclusive), KWArg("clamp", clamp)]


class Below(StreamMethod):

    def __init__(self, limit, inclusive=None, clamp=None):
        """Only pass through data in the stream that is below a particular
           value, or clamp data below a value to that value.
        """
        super(Below, self).__init__("below")
        self.args = [StrArg(limit), KWArg(
            "inclusive", inclusive), KWArg("clamp", clamp)]


class Between(StreamMethod):

    def __init__(self, low_limit, high_limit,
                 low_inclusive=None, high_inclusive=None, clamp=None):
        """Only pass through data in the stream that is between two particular
           values or replace data that is not between two particular values
           with the limit that they are closest to.
        """
        super(Between, self).__init__("between")
        self.args = [
            StrArg(low_limit),
            StrArg(high_limit),
            KWArg("low_inclusive", low_inclusive),
            KWArg("high_inclusive", high_inclusive),
            KWArg("clamp", clamp)
        ]


class Equals(StreamMethod):

    def __init__(self, value, replacement=None):
        """Only pass through data in the stream that is equal to a particular
           value or replace data that is not equal to a particular value with
           another value.
        """
        super(Equals, self).__init__("equals")
        self.args = [StrArg(value), KWArg("replacement", replacement)]


class Not_between(StreamMethod):

    def __init__(self, low_limit, high_limit,
                 low_inclusive=None, high_inclusive=None):
        """Only pass through data in the stream that is not between two
           particular values.
        """
        super(Not_between, self).__init__("not_between")
        self.args = [
            StrArg(low_limit),
            StrArg(high_limit),
            KWArg("low_inclusive", low_inclusive),
            KWArg("high_inclusive", high_inclusive)
        ]


class Not_equals(StreamMethod):

    def __init__(self, value, replacement=None):
        """Only pass through data in the stream that is not equal to a
           particular value or replace data that is equal to a particular
           value with another value.
        """
        super(Not_equals, self).__init__("not_equals")
        self.args = [StrArg(value), KWArg("replacement", replacement)]


class Promote(StreamMethod):

    def __init__(self, *properties):
        """Promotes a metadata property to a dimension."""
        super(Promote, self).__init__("promote")
        self.args = [Arg(list(properties))]

class Fill(StreamMethod):
    def __init__(self, value, duration):
        """Fills in missing values for time series in a stream."""
        super(Fill, self).__init__("fill")
        self.args = [
            KWArg("value", value),
            KWArg("duration", duration),
        ]

class Integrate(StreamMethod):
    def __init__(self):
        super(Integrate, self).__init__("integrate")
        self.args = []

class Kpss(StreamMethod):
    def __init__(self, over, mode):
        """Fills in missing values for time series in a stream."""
        super(Kpss, self).__init__("kpss")
        if mode not in set(['level', 'trend']):
            raise ValueError('kpss mode must be level|trend')

        self.args = [
            KWArg("over", over),
            KWArg("mode", mode),
        ]

class RateOfChange(StreamMethod):
    def __init__(self):
        super(RateOfChange, self).__init__("rateofchange")
        self.args = []    

class Ref(Arg):

    def __init__(self, arg):
        super(self.__class__, self).__init__(arg)


class Dimensions(StreamMethod):

    def __init__(self, aliases=None, renames=None):
        super(Dimensions, self).__init__("dimensions")
        if not aliases and not renames:
            raise ValueError("Either aliases or renames must be defined, but not both.")

        self.args = [KWArg("aliases", aliases), KWArg("renames", renames)]
