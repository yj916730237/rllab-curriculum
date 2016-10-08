import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""


import tensorflow as tf
from rllab.misc.instrument import stub, run_experiment_lite
from sandbox.rocky.cirrascale.launch_job import launch_cirrascale
from rllab import config

from sandbox.rocky.tf.policies.rnn_utils import NetworkType

# stub(globals())

from rllab.misc.instrument import VariantGenerator, variant

"""
Test performance of new network
"""

USE_GPU = True#False  # True#False  # True#False
USE_CIRRASCALE = True#False  # True
MODE = "local_docker"#launch_cirrascale#(##)"local_docker"
MODE = launch_cirrascale
SETUP = "conopt"
ENV = "particle-2"
VERSION = "v5"


# SETUP = "simple"


class VG(VariantGenerator):
    @variant
    def seed(self):
        return [11, 21, 31]

    @variant
    def n_train_trajs(self):
        return [5000, 1000, 300]

    @variant
    def use_shuffler(self):
        return [True]#False, True]#, False]#, True]

    @variant
    def state_include_action(self):
        return [False]#, True]#, False]#, True]

    @variant
    def horizon(self):
        return [30]#, 100]

    @variant
    def n_epochs(self):
        return [1000]

    @variant
    def obs_type(self):
        return ["full_state"]#"full_state"]#, "image"]

    @variant
    def obs_size(self):
        yield (30, 30)

    @variant(hide=True)
    def demo_cache_key(self, horizon, obs_type):
        yield "%s-%s-%s-%s-%s" % (
            SETUP,
            ENV,
            str(horizon),
            obs_type.replace("_", "-"),
            VERSION
        ),


vg = VG()

variants = vg.variants()

print("#Experiments: %d" % len(variants))


def run_task(v):
    from sandbox.rocky.analogy.algos.trainer import Trainer
    from sandbox.rocky.analogy.demo_collector.policy_demo_collector import PolicyDemoCollector
    from sandbox.rocky.analogy.demo_collector.trajopt_demo_collector import TrajoptDemoCollector
    from sandbox.rocky.analogy.envs.conopt_particle_env import ConoptParticleEnv
    from sandbox.rocky.analogy.envs.simple_particle_env import SimpleParticleEnv
    from sandbox.rocky.analogy.policies.conopt_particle_tracking_policy import ConoptParticleTrackingPolicy
    from sandbox.rocky.analogy.policies.simple_particle_tracking_policy import SimpleParticleTrackingPolicy
    from sandbox.rocky.analogy.policies.demo_rnn_mlp_analogy_policy1 import DemoRNNMLPAnalogyPolicy
    # import sandbox.rocky.analogy.networks.conopt_particle_networks as net
    import sandbox.rocky.analogy.networks.conopt_particle.small as net
    from sandbox.rocky.tf.envs.base import TfEnv

    env = TfEnv(ConoptParticleEnv(
        seed=0,
        obs_type=v["obs_type"],
        obs_size=v["obs_size"]
    ))

    obs_embedding_net = net.StateObsEmbeddingNetwork(env_spec=env.spec)
    action_embedding_net = net.ActionEmbeddingNetwork(env_spec=env.spec)
    summary_net = net.SummaryNetwork(
        env_spec=env.spec,
        obs_embedding_network=obs_embedding_net,
        action_embedding_network=action_embedding_net
    )
    action_net = net.ActionNetwork(
        env_spec=env.spec,
        obs_embedding_network=obs_embedding_net,
        summary_network=summary_net,
    )

    policy = DemoRNNMLPAnalogyPolicy(
        env_spec=env.spec,
        name="policy",
        summary_network=summary_net,
        action_network=action_net,
    )

    algo = Trainer(
        policy=policy,
        env_cls=TfEnv.wrap(
            ConoptParticleEnv if SETUP == "conopt" else
            SimpleParticleEnv,
            obs_type=v["obs_type"],
            obs_size=v["obs_size"],
        ),
        demo_collector=PolicyDemoCollector(
            policy_cls=ConoptParticleTrackingPolicy if SETUP == "conopt" else
            SimpleParticleTrackingPolicy
        ),
        skip_eval=True,
        demo_cache_key=v["demo_cache_key"],
        n_train_trajs=v["n_train_trajs"],
        n_test_trajs=50,
        horizon=v["horizon"],
        n_epochs=v["n_epochs"],
        learning_rate=1e-2,
        no_improvement_tolerance=20,
        shuffler=ConoptParticleEnv.shuffler() if v["use_shuffler"] else None,
        batch_size=512,
    )
    algo.train()

config.DOCKER_IMAGE = "dementrock/rllab3-conopt-gpu-cuda80"
config.KUBE_DEFAULT_NODE_SELECTOR = {
}
config.KUBE_DEFAULT_RESOURCES = {
    "requests": {
        "cpu": 8,
        "memory": "10Gi",
    },
}


# all_cache_keys = set([v["demo_cache_key"] for v in variants])
# for cache_key in all_cache_keys:
#     v = [v for v in variants if v["demo_cache_key"] == cache_key][0]
#     print("Warm-starting cache for %s" % cache_key)
#     run_experiment_lite(
#         run_task,
#         use_cloudpickle=True,
#         exp_prefix="tmp",
#         mode="local_docker",
#         n_parallel=8,
#         seed=v["seed"],
#         snapshot_mode="last",
#         variant=dict(v, n_epochs=1),
#         terminate_machine=True,
#         sync_all_data_node_to_s3=False,
#         pre_commands=[
#             "Xdummy :12 & export DISPLAY=:12"
#         ]
#     )

# First, make sure that all

for v in variants:
    run_experiment_lite(
        run_task,
        use_cloudpickle=True,
        exp_prefix="conopt-particle-2-2",
        mode=MODE,
        n_parallel=0,
        seed=v["seed"],
        snapshot_mode="last",
        variant=v,
        terminate_machine=True,
        sync_all_data_node_to_s3=False,
        use_gpu=USE_GPU,
        env=dict(
            AWS_ACCESS_KEY_ID=config.AWS_ACCESS_KEY,
            AWS_SECRET_ACCESS_KEY=config.AWS_ACCESS_SECRET,
        ) if MODE == "local_docker" else None,
        # pre_commands=[
        #     "Xdummy :12 & export DISPLAY=:12"
        # ]
    )
    # sys.exit()
