from sandbox.rocky.tf.algos.trpo import TRPO
from rllab.baselines.linear_feature_baseline import LinearFeatureBaseline
from sandbox.bradly.third_person.envs.old.point_images import PointEnv
from rllab.envs.normalized_env import normalize
from sandbox.bradly.third_person.policy.gaussian_conv_policy import GaussianConvPolicy
from sandbox.rocky.tf.envs.base import TfEnv
from rllab.misc.instrument import stub, run_experiment_lite
from sandbox.rocky.tf.optimizers.conjugate_gradient_optimizer import ConjugateGradientOptimizer, FiniteDifferenceHvp


stub(globals())

env = TfEnv(normalize(PointEnv(should_render=True)))

n_layers = 1
conv_filters = (5,)*n_layers
conv_filter_sizes = (5,)*n_layers
conv_pads = ('SAME',)*n_layers
conv_strides = (3,)*n_layers

policy = GaussianConvPolicy(
    name="policy",
    env_spec=env.spec,
    # The neural network policy should have two FF layers, each with 32 hidden units.
    hidden_sizes=(32, 32),
    conv_filters=conv_filters,
    conv_filter_sizes=conv_filter_sizes,
    conv_pads=conv_pads,
    conv_strides=conv_strides,
)

baseline = LinearFeatureBaseline(env_spec=env.spec)

algo = TRPO(
    env=env,
    policy=policy,
    baseline=baseline,
    batch_size=4000,
    max_path_length=100,
    n_itr=40,
    discount=0.99,
    step_size=0.01,
    optimizer=ConjugateGradientOptimizer(hvp_approach=FiniteDifferenceHvp(base_eps=1e-5))
)
run_experiment_lite(
    algo.train(),
    n_parallel=4,
    seed=1,
)