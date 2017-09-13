import os
import random

os.environ['THEANO_FLAGS'] = 'floatX=float32,device=cpu'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import argparse
import sys
from multiprocessing import cpu_count
from rllab.misc.instrument import run_experiment_lite
from rllab.misc.instrument import VariantGenerator
from sandbox.carlos_snn.autoclone import autoclone
from rllab import config

from sandbox.ignasi.robust_disk.pr2_disk_trpo_algo import run_task

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--ec2', '-e', action='store_true', default=False, help="add flag to run in ec2")
    parser.add_argument('--clone', '-c', action='store_true', default=False,
                        help="add flag to copy file and checkout current")
    parser.add_argument('--local_docker', '-d', action='store_true', default=False,
                        help="add flag to run in local dock")
    parser.add_argument('--type', '-t', type=str, default='', help='set instance type')
    parser.add_argument('--price', '-p', type=str, default='', help='set betting price')
    parser.add_argument('--subnet', '-sn', type=str, default='', help='set subnet like us-west-1a')
    parser.add_argument('--name', '-n', type=str, default='', help='set exp prefix name and new file name')
    parser.add_argument('--debug', action='store_true', default=False, help="run code without multiprocessing")
    args = parser.parse_args()

    if args.clone:
        autoclone.autoclone(__file__, args)

    # setup ec2
    subnets = [
        'ap-southeast-2b', 'ap-southeast-2c', 'ap-southeast-1a', 'eu-central-1b', 'eu-west-1a', 'eu-west-1b',
        'eu-west-1c'
    ]
    # subnets = [
    #     'ap-northeast-2a', 'ap-northeast-2c', 'us-east-2b', 'ap-south-1a', 'us-east-2c', 'us-east-2a', 'ap-south-1b',
    #     'us-east-1b', 'us-east-1a', 'us-east-1d', 'us-east-1e', 'eu-west-1c', 'eu-west-1a', 'eu-west-1b'
    # ]
    ec2_instance = args.type if args.type else 'm4.16xlarge'
    # configure instan
    info = config.INSTANCE_TYPE_INFO[ec2_instance]
    config.AWS_INSTANCE_TYPE = ec2_instance
    config.AWS_SPOT_PRICE = str(info["price"])
    n_parallel = int(info["vCPU"] / 2)  # make the default 4 if not using ec2
    if args.ec2:
        mode = 'ec2'
    elif args.local_docker:
        mode = 'local_docker'
        n_parallel = cpu_count() if not args.debug else 1
    else:
        mode = 'local'
        n_parallel = cpu_count() if not args.debug else 1
        # n_parallel = multiprocessing.cpu_count()


    vg = VariantGenerator()
    vg.add('start_size', [9])  # for the generation it's +2!!
    # vg.add('start_bounds',
    #        [[(-2.2854, -.05236, -3.9, -2.3213, -3.15, -2.094, -3.15, 0, 0),
    #          (1.714602, 1.3963, 0.0, 0.0, 3.15, 0.0, 3.15, 0, 0)]])
    # vg.add('start_goal', [(0.386884635, 1.13705218, -2.02754147, -1.74429440, 2.02916096, -0.873269847, 1.54785694)])
    vg.add('start_goal', [[ 1.38781535, -0.2317441, 2.65237236, -1.94273868, 4.78109335,-0.90467269, -1.56926878, 0, 0]])
    vg.add('ultimate_goal', [(0.4146814, 0.47640087, 0.5305665)])
    vg.add('goal_size', [3]) # changed
    vg.add('terminal_eps', [0.03])

    vg.add('physics_variances', [[0, 0, 0, 0], [0.01, 0.005, 0.01, 0.05]])  # damping, armature, frictionloss, mass
    # goal-algo params
    vg.add('ctrl_regularizer_weight', [1])
    vg.add('action_torque_lambda', [1])
    vg.add('inner_weight', [1e-3])
    vg.add('goal_weight', lambda inner_weight: [1000] if inner_weight > 0 else [1])
    vg.add('distance_metric', ['L2'])
    vg.add('extend_dist_rew', [False])
    vg.add('persistence', [1])
    vg.add('with_replacement', [True])
    vg.add('n_traj', [3])   #  if use_trpo_paths it uses 2!
    vg.add('num_new_starts', [300])
    # sampling params
    vg.add('horizon', [100])
    vg.add('outer_iters', [5000])
    vg.add('inner_iters', [5])  # again we will have to divide/adjust the
    vg.add('pg_batch_size', [50000])
    # policy initialization
    vg.add('output_gain', [0.1])
    vg.add('policy_init_std', [1])
    vg.add('learn_std', [False])
    vg.add('adaptive_std', [False])
    vg.add('discount', [0.995])
    vg.add('baseline', ["g_mlp"])
    vg.add('policy', ['mlp'])
    # vg.add('policy', ['mlp'])
    # vg.add('policy', ['recurrent', 'mlp'])
    vg.add('trunc_steps', [100])

    # vg.add('seed', range(100, 600, 100))
    vg.add('seed', [100, 200, 300, 400, 500])

    vg.add('move_peg', [True]) # whether or not to move peg
    vg.add('kill_radius', [0.3])
    vg.add('kill_peg_radius', [0.03])
    vg.add('max_gen_states', [300])
    vg.add('peg_positions', [(7,8)])  # joint numbers for peg
    vg.add('peg_scaling', [10]) # multiplicative factor to peg position

    exp_prefix = 'robust-disk-trpo'
    # Launching
    print("\n" + "**********" * 10 + "\nexp_prefix: {}\nvariants: {}".format(exp_prefix, vg.size))
    print('Running on type {}, with price {}, parallel {} on the subnets: '.format(config.AWS_INSTANCE_TYPE,
                                                                                   config.AWS_SPOT_PRICE, n_parallel),
          *subnets)

    for vv in vg.variants():
        if mode in ['ec2', 'local_docker']:
            # choose subnet
            subnet = random.choice(subnets)
            config.AWS_REGION_NAME = subnet[:-1]
            config.AWS_KEY_NAME = config.ALL_REGION_AWS_KEY_NAMES[
                config.AWS_REGION_NAME]
            config.AWS_IMAGE_ID = config.ALL_REGION_AWS_IMAGE_IDS[
                config.AWS_REGION_NAME]
            config.AWS_SECURITY_GROUP_IDS = \
                config.ALL_REGION_AWS_SECURITY_GROUP_IDS[
                    config.AWS_REGION_NAME]
            config.AWS_NETWORK_INTERFACES = [
                dict(
                    SubnetId=config.ALL_SUBNET_INFO[subnet]["SubnetID"],
                    Groups=config.AWS_SECURITY_GROUP_IDS,
                    DeviceIndex=0,
                    AssociatePublicIpAddress=True,
                )
            ]

            run_experiment_lite(
                # use_cloudpickle=False,
                stub_method_call=run_task,
                variant=vv,
                mode=mode,
                # Number of parallel workers for sampling
                n_parallel=n_parallel,
                # Only keep the snapshot parameters for the last iteration
                snapshot_mode="last",
                seed=vv['seed'],
                plot=True,
                exp_prefix=exp_prefix,
                # exp_name=exp_name,
                # for sync the pkl file also during the training
                sync_s3_pkl=True,
                # sync_s3_png=True,
                sync_s3_html=True,
                # # use this ONLY with ec2 or local_docker!!!
                pre_commands=[
                    'export MPLBACKEND=Agg',
                    'pip install --upgrade pip',
                    'pip install --upgrade -I tensorflow',
                    'pip install git+https://github.com/tflearn/tflearn.git',
                    'pip install dominate',
                    'pip install multiprocessing_on_dill',
                    'pip install scikit-image',
                    'conda install numpy -n rllab3 -y',
                ],
                # terminate_machine=False,
            )
            #sys.exit()
            # if mode == 'local_docker':
            #     sys.exit()
        else:
            # run_task(vv)
            # import pdb;
            # pdb.set_trace()
            run_experiment_lite(
                # use_cloudpickle=False,
                stub_method_call=run_task,
                variant=vv,
                mode='local',
                n_parallel=n_parallel,
                # Only keep the snapshot parameters for the last iteration
                snapshot_mode="last",
                seed=vv['seed'],
                exp_prefix=exp_prefix,
                plot=True,
                # exp_name=exp_name,
            )
            sys.exit()