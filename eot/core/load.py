import os
from importlib import import_module
from eot.config.pipeline_config import WrappedAIConfig

#
# Import module
#
def load_module(module):
    module = import_module(module)
    assert module, "Unable to import module {}".format(module)
    return module


#
# Config
#
def load_config(toml_ifp):
    pipeline_config = WrappedAIConfig.get_from_file(
        os.path.expanduser(toml_ifp)
    )
    return pipeline_config.ai_config
