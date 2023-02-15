import os
import pathlib
import logging
from utils import constants, configmap_util, utils
import argparse


logging.basicConfig(
    format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S'
)


# Parse command line arguments
def cmd_args_parser() -> dict:
    parser = argparse.ArgumentParser(description="NextGenRoutes migration tool usage options",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-f", "--cis-file", help="path of the cis deployment file")
    parser.add_argument("-d", "--cis-name", help="path of the cis deployment name")
    parser.add_argument("-cm", "--cm-file", help="path of the configmap file")
    parser.add_argument("-o", "--output", help="path of the output directory")
    parser.add_argument('-log', '--loglevel', default='INFO',
                        help='log level. Example --loglevel INFO, ERROR, DEBUG, WARNING')
    parsed_args = parser.parse_args()
    args_dict = vars(parsed_args)
    final_values = dict()
    script_dir = pathlib.Path(__file__).parent.resolve()
    if args_dict:
        if args_dict['cis-file']:
            final_values['cis-file'] = args_dict['cis-file']

        if args_dict['cis-name']:
            final_values['cis-name'] = args_dict['cis-name']

        if args_dict['cm-file']:
            final_values['cm-file'] = args_dict['cm-file']

        if args_dict['output']:
            final_values['output_dir'] = args_dict['output']
            if final_values['output_dir'][-1] != "/":
                final_values['output_dir'] += "/"
        else:
            final_values['output_dir'] = str(script_dir) + "/" + constants.DEFAULT_OUTPUT_DIR + "/"

    if args_dict['loglevel'] == "DEBUG":
        logging.getLogger().setLevel(logging.DEBUG)
    elif args_dict['loglevel'] == "ERROR":
        logging.getLogger().setLevel(logging.ERROR)
    elif args_dict['loglevel'] == "WARNING":
        logging.getLogger().setLevel(logging.WARNING)
    else:
        logging.getLogger().setLevel(logging.INFO)
    return final_values


# Validate the inputs
def validate_inputs(cli_args):
    if 'cis-file' not in cli_args and 'cis-name' not in cli_args:
        logging.error("Either provide cis-file (CIS deployment yaml file) or cis-name (name of the CIS deployment in "
                      "the format namespace/deployment-name)")
        exit()

    # check cis deployment file exists
    if 'cis-file' in cli_args and not os.path.isfile(args_values['cis-file']):
        logging.error('CIS deployment file %s does not exist', args_values['cis-file'])
        exit()

    # check output directory exists else create
    if not os.path.exists(args_values['output_dir']):
        os.makedirs(args_values['output_dir'])


if __name__ == '__main__':
    try:
        # Parse CLI parameters
        args_values = cmd_args_parser()
        # Validate inputs
        validate_inputs(args_values)
        # Read CIS deployment config
        cis_deploy_obj = dict()
        if 'cis-file' in args_values:
            cis_deploy_obj = utils.read_yaml(args_values['cis-file'])
        elif 'cis-name' in args_values:
            cis_deploy_obj = utils.get_deploy_res_from_deploy(args_values['cis-name'])
        else:
            logging.error("Invalid input provided")
            exit()
        if not cis_deploy_obj or len(cis_deploy_obj) == 0:
            logging.error("CIS deployment configuration couldn't be fetched")
            exit()
        cis_args = utils.get_cis_args_from_deployment(cis_deploy_obj)
        if len(cis_args) == 0:
            logging.error("CIS deployment configuration doesn't exist.")
            exit()
        cis_args_dict = utils.convert_container_args_to_dict(cis_args)

        # Create policy CR if override-as3-configmap is used or user wants to use it
        # Read override-configmap
        policy_cr = ""
        if 'cm-file' in args_values:
            cm_obj = utils.read_yaml(args_values['cm-file'])
            policy = utils.get_policy_from_cm_obj(cm_obj=cm_obj)
            utils.generate_policy_yaml(policy, dest_path=args_values['output_dir'] + "/policy.yaml")
            policy_cr = policy['metadata']['namespace'] + '/' + policy['metadata']['name']

        # Create configmap
        configmap_util.generate_config_map_with_base_route_group(cis_args_dict,
                                                                 namespace=cis_deploy_obj['metadata']['namespace'],
                                                                 policy_cr=policy_cr,
                                                                 output_path=args_values['output_dir'])

        # Create CIS deployment yaml
        utils.prepare_cis_config_for_nextgen_routes(cis_args_dict, cis_deploy_obj)
        utils.generate_cis_deployment_yaml(cis_deploy_obj, args_values['output_dir']+"/"+ constants.CIS_DEPLOY_FILE)

        print("Successfully generated the configmap and CIS deployment file in the following directory: "
              "{}".format(args_values['output_dir']))
        print("Apply the generated configmap and CIS deployment using the following command:")
        print("kubectl apply -f {}".format(args_values['output_dir']))

    except Exception as ex:
        logging.error(ex)
    
