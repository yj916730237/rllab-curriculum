import lasagne.layers as L
import lasagne.nonlinearities as NL
import numpy as np
import theano.tensor as TT
from rllab.core.lasagne_powered import LasagnePowered
from rllab.core.network import GRUNetwork
from rllab.core.serializable import Serializable
from rllab.misc.overrides import overrides
from rllab.misc import special
from rllab.misc import ext
from rllab.policy.base import StochasticPolicy
from rllab.misc import categorical_dist


class CategoricalGRUPolicy(StochasticPolicy, LasagnePowered, Serializable):

    def __init__(
            self,
            mdp_spec,
            hidden_sizes=(32,),
            include_action=True,
            nonlinearity=NL.rectify):
        """
        :param mdp_spec: A spec for the mdp.
        :param hidden_sizes: list of sizes for the fully connected hidden layers
        :param nonlinearity: nonlinearity used for each hidden layer
        :return:
        """
        Serializable.quick_init(self, locals())
        super(CategoricalGRUPolicy, self).__init__(mdp_spec)

        assert len(hidden_sizes) == 1

        if include_action:
            input_shape = (mdp_spec.observation_dim + mdp_spec.action_dim,)
        else:
            input_shape = (mdp_spec.observation_dim,)

        prob_network = GRUNetwork(
            input_shape=input_shape,
            output_dim=mdp_spec.action_dim,
            hidden_dim=hidden_sizes[0],
            nonlinearity=nonlinearity,
            output_nonlinearity=NL.softmax,
        )

        self._prob_network = prob_network
        self._include_action = include_action

        self._f_prob = ext.compile_function(
            [
                prob_network.step_input_layer.input_var,
                prob_network.step_prev_hidden_layer.input_var
            ],
            L.get_output([
                prob_network.step_output_layer,
                prob_network.step_hidden_layer
            ])
        )

        self._prev_action = None
        self._prev_hidden = None
        self._hidden_sizes = hidden_sizes

        self.reset()

        LasagnePowered.__init__(self, [prob_network.output_layer])

    def _get_prev_action_var(self, action_var):
        n_batches = action_var.shape[0]
        action_dim = action_var.shape[2]
        return TT.concatenate([
            TT.zeros((n_batches, 1, action_dim)),
            action_var[:, :-1, :]
        ], axis=1)

    @overrides
    def get_pdist_sym(self, obs_var, action_var):
        n_batches, n_steps = obs_var.shape[:2]
        obs_var = obs_var.reshape((n_batches, n_steps, -1))
        if self._include_action:
            prev_action_var = self._get_prev_action_var(action_var)
            all_input_var = TT.concatenate(
                [obs_var, prev_action_var],
                axis=2
            )
        else:
            all_input_var = obs_var
        return L.get_output(
            self._prob_network.output_layer,
            {self._prob_network.input_layer: all_input_var}
        )

    @overrides
    def kl(self, old_prob_var, new_prob_var):
        return categorical_dist.kl_sym(old_prob_var, new_prob_var)

    @overrides
    def likelihood_ratio(self, old_prob_var, new_prob_var, action_var):
        return categorical_dist.likelihood_ratio_sym(
            action_var, old_prob_var, new_prob_var)

    @overrides
    def compute_entropy(self, pdist):
        return np.mean(categorical_dist.entropy(pdist))

    @property
    @overrides
    def pdist_dim(self):
        return self.action_dim

    def reset(self):
        self._prev_action = np.zeros((self.action_dim,))
        self._prev_hidden = self._prob_network.hid_init_param.get_value()##np.zeros((self._hidden_sizes[0],))

    # The return value is a pair. The first item is a matrix (N, A), where each
    # entry corresponds to the action value taken. The second item is a vector
    # of length N, where each entry is the density value for that action, under
    # the current policy
    @overrides
    def get_action(self, observation):
        if self._include_action:
            all_input = np.concatenate([observation.flatten(), self._prev_action])
        else:
            all_input = observation.flatten()
        prob, hidden_vec = [x[0] for x in self._f_prob([all_input], [self._prev_hidden])]
        action = special.weighted_sample(prob, xrange(self.action_dim))
        action_vec = special.to_onehot(action, self.action_dim)
        self._prev_action = action_vec
        self._prev_hidden = hidden_vec
        return action_vec, prob

    @property
    @overrides
    def is_recurrent(self):
        return True