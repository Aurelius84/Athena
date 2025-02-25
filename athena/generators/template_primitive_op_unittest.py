import os
os.environ['FLAGS_cinn_new_group_scheduler'] = '1'
os.environ['FLAGS_group_schedule_tiling_first'] = '1'
os.environ['FLAGS_enable_pir_api'] = '1'
os.environ['FLAGS_cinn_bucket_compile'] = '1'
import sys
import unittest
import numpy as np
from dataclasses import dataclass
import typing as t

@dataclass
class Stage:
    name: str
    env_vars: t.Dict[str, str]

cinn_stages = [
    Stage(
        name="dynamic_to_static",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=False,
            FLAGS_prim_enable_dynamic=False,
        ),
    ),
    Stage(
        name="prim",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
        ),
    ),
    Stage(
        name="infer_symbolic",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=False,
            FLAGS_check_infer_symbolic=True,
        ),
    ),
	Stage(
        name="frontend",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=True,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=True,
            FLAGS_check_infer_symbolic=False,
            FLAGS_enable_fusion_fallback=True,
        ), 
    ),
    Stage(
        name="backend",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=True,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=True,
            FLAGS_check_infer_symbolic=False,
            FLAGS_enable_fusion_fallback=False,
        ), 
    ),
]

def GetCinnStageByName(name):
    for stage in cinn_stages:
        if stage.name == name:
            return stage
    return None

def GetCurrentCinnStage():
    name = os.getenv('PADDLE_DEBUG_CINN_STAGE_NAME')
    if name is None:
        return None
    stage_names = [stage.name for stage in cinn_stages]
    assert name in stage_names, (
        f"PADDLE_DEBUG_CINN_STAGE_NAME should be in {stage_names}"
    )
    return GetCinnStageByName(name)

def GetPrevCinnStage(stage):
    for i in range(1, len(cinn_stages)):
        if stage is cinn_stages[i]:
            return cinn_stages[i - 1]
    return None

def IsCinnStageEnableDiff():
    value = os.getenv('PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF')
    enabled = value in {
        '1',
        'true',
        'True',
    }
    if enabled:
        assert GetCurrentCinnStage() is not None
    return enabled

def GetExitCodeAndStdErr(cmd, env):
    import subprocess
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    return result.returncode, result.stderr

def GetStageExitCodeAndStdErr(stage):
    return GetExitCodeAndStdErr(
        [sys.executable, __file__],
        env=dict(
            PADDLE_DEBUG_CINN_STAGE_NAME=stage.name,
            PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF='0',
            PYTHONPATH=os.getenv('PYTHONPATH'),
            ATHENA_ENABLE_TRY_RUN="False",
        ),
    )

def AthenaTryRunEnabled():
    return os.getenv('ATHENA_ENABLE_TRY_RUN') not in {
        "0",
        "False",
        "false",
        "OFF"
    }

def GetNeedSkipAndSkipMessage():
    current_stage = GetCurrentCinnStage()
    assert current_stage is not None
    if not IsCinnStageEnableDiff():
        return False, ""
    last_stage = GetPrevCinnStage(current_stage)
    if last_stage is None:
        return False, ""
    exitcode, stderr = GetStageExitCodeAndStdErr(last_stage)
    if exitcode != 0:
        return True, f"last stage failed. stderr: {stderr}"
    return False, ""

def GetCurrentStageTryRunExitCodeAndStdErr():
    if not AthenaTryRunEnabled():
        return False, ""
    current_stage = GetCurrentCinnStage()
    assert current_stage is not None
    return GetStageExitCodeAndStdErr(current_stage)

def SetDefaultEnv(**env_var2value):
    for env_var, value in env_var2value.items():
        if os.getenv(env_var) is None:
            os.environ[env_var] = str(value)

SetDefaultEnv(
    PADDLE_DEBUG_CINN_STAGE_NAME="backend",
    PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF=False,
    PADDLE_DEBUG_ENABLE_CINN=True,
    FLAGS_enable_pir_api=True,
    FLAGS_prim_all=True,
    FLAGS_prim_enable_dynamic=True,
    FLAGS_use_cinn=False,
    FLAGS_check_infer_symbolic=False,
    FLAGS_enable_fusion_fallback=False,
)

import paddle

def SetEnvVar(env_var2value):
    for env_var, value in env_var2value.items():
        os.environ[env_var] = str(value)
    paddle.set_flags({
        env_var:value
        for env_var, value in env_var2value.items()
        if env_var.startswith('FLAGS_')
    })

if GetCurrentCinnStage() is not None:
    SetEnvVar(GetCurrentCinnStage().env_vars)

def GetEnvVarEnableJit():
    enable_jit = os.getenv('PADDLE_DEBUG_ENABLE_JIT')
    return enable_jit not in {
        "0",
        "False",
        "false",
        "OFF",
    }

def GetEnvVarEnableCinn():
    enable_cinn = os.getenv('PADDLE_DEBUG_ENABLE_CINN')
    if enable_cinn is None:
        return {{PADDLE_DEBUG_ENABLE_CINN}}
    return enable_cinn not in {
        "0",
        "False",
        "false",
        "OFF",
    }


def GetTolerance(dtype):
    if dtype == np.float16:
        return GetFloat16Tolerance()
    if dtype == np.float32:
        return GetFloat32Tolerance()
    return 1e-6

def GetFloat16Tolerance():
    try:
        return float(os.getenv('PADDLE_DEBUG_FLOAT16_TOL'))
    except:
        return 1e-3

def GetFloat32Tolerance():
    try:
        return float(os.getenv('PADDLE_DEBUG_FLOAT32_TOL'))
    except:
        return 1e-6

def IsInteger(dtype):
    return np.dtype(dtype).char in np.typecodes['AllInteger']

def ApplyToStatic(net, use_cinn):
    build_strategy = paddle.static.BuildStrategy()
    build_strategy.build_cinn_pass = use_cinn
    return paddle.jit.to_static(
        net,
        input_spec=net.get_input_spec(),
        build_strategy=build_strategy,
        full_graph=True,
    )

class InstanceTrait:

    @classmethod
    def instance(cls):
        if cls.instance_ is None:
            cls.instance_ = cls()
        return cls.instance_

    @classmethod
    def static_instance_with_cinn(cls):
        if cls.static_instance_with_cinn_ is None:
            cls.static_instance_with_cinn_ = ApplyToStatic(
                cls.instance(),
                use_cinn=True
            )
        return cls.static_instance_with_cinn_

    @classmethod
    def static_instance_without_cinn(cls):
        if cls.static_instance_without_cinn_ is None:
            cls.static_instance_without_cinn_ = ApplyToStatic(
                cls.instance(),
                use_cinn=False
            )
        return cls.static_instance_without_cinn_


class CinnTestBase:

    def setUp(self):
        paddle.seed(2024)
        self.prepare_data()

    def _test_entry(self):
        dy_outs = self.train(use_cinn=False)
        cinn_outs = self.train(use_cinn=GetEnvVarEnableCinn())

        for cinn_out, dy_out in zip(cinn_outs, dy_outs):
          if type(cinn_out) is list and type(dy_out) is list:
            for x, y in zip(cinn_out, dy_out):
              self.assert_all_close(x, y)
          else:
            self.assert_all_close(cinn_out, dy_out)

    def train(self, use_cinn):
        if GetEnvVarEnableJit():
            net = self.prepare_static_net(use_cinn)
        else:
            net = self.prepare_net()
        paddle.seed(2024)
        out = net(*self.inputs)
        return out
    
    def prepare_data(self):
        self.inputs = self.get_inputs()
        for input in self.inputs:
            input.stop_gradient = True

    def prepare_net(self):
        return self.get_test_class().instance()

    def prepare_static_net(self, use_cinn):
        if use_cinn:
            return self.get_test_class().static_instance_with_cinn()
        else:
            return self.get_test_class().static_instance_without_cinn()

    def assert_all_close(self, x, y):
        if (hasattr(x, "numpy") and hasattr(y, "numpy")):
            x_numpy = x.numpy()
            y_numpy = y.numpy()
            assert x_numpy.dtype == y_numpy.dtype
            if IsInteger(x_numpy.dtype):
                np.testing.assert_equal(x_numpy, y_numpy)
            else:
                tol = GetTolerance(x_numpy.dtype)
                np.testing.assert_allclose(x_numpy, y_numpy, atol=tol, rtol=tol)
        else:
            assert x == y

{% macro get_input_tensor_instance(tensor_meta) -%}
{%- set shape = tensor_meta.shape -%}
{%- set dtype = tensor_meta.dtype -%}
{%- set big_dtype = tensor_meta.big_dtype -%}
{%- set data = tensor_meta.data -%}
{%- set min = tensor_meta.min -%}
{%- set max = tensor_meta.max -%}
{%- if data != None -%}
    {%- if data == [] and shape == [] -%}
    paddle.to_tensor({{data}}, dtype='{{dtype}}')
    {%- else -%}
    paddle.to_tensor({{data}}, dtype='{{dtype}}').reshape({{shape}})
    {%- endif -%}
{%- elif big_dtype == "bool" -%}
    paddle.cast(paddle.randint(low=0, high=2, shape={{shape}}, dtype='int32'), 'bool')
{%- elif big_dtype == "int64" -%}
    paddle.randint(low={{min}}, high={{max}}, shape={{shape}}, dtype='{{dtype}}')
{%- elif big_dtype == "float64" -%}
    paddle.uniform({{shape}}, dtype='{{dtype}}', min={{min}}, max={{max}})
{%- endif -%}
{%- endmacro %}

{% macro get_operand_value(op, operand_id) -%}
{%- set data = op.example_input_data4operand_id(operand_id) -%}
{%- set immediate_value = op.immediate_value4operand_id(operand_id, data) -%}
{%- set null_tensor_id = op.null_tensor_id4operand_id(operand_id) -%}
{%- set operand_tensor_id = op.operand_tensor_id4operand_id(operand_id) -%}
{%- set tensor_list_member_ids = op.tensor_list_member_ids4operand_id(operand_id) -%}
{%- if data != None and immediate_value != None -%}
    {{immediate_value}}
{%- elif null_tensor_id != None -%}
    None
{%- elif operand_tensor_id != None -%}
    {{op.tensor_name4tensor_id(operand_tensor_id)}}
{%- elif tensor_list_member_ids != None -%}
    [{%- for member_tensor_id in tensor_list_member_ids -%}
    {%- if loop.index0 > 0 -%}{{", "}}{%- endif -%}
    {{op.tensor_name4tensor_id(member_tensor_id)}}
    {%- endfor -%}]
{%- endif -%}
{%- endmacro %}

{% macro get_primitive_class_methods(op) %}
    def __init__(self):
        super().__init__()

    def forward(self{{", "}}
        {%- for tensor_id in op.tensor_ids -%}
        {%- if loop.index0 > 0 -%}{{", "}}{%- endif -%}
        {{op.tensor_name4tensor_id(tensor_id)}}
        {%- endfor -%}
    ):
        {%- for operand_id in op.operand_ids %}
        {{op.tensor_name4operand_id(operand_id)}} = {{get_operand_value(op, operand_id)}}
        {%- endfor %}
        return {{ op.op_expr }}

    def get_input_spec(self):
        return [
        {%- for tensor_id in op.tensor_ids %}
        {%- set shape, dtype = op.input_spec_shape_dtype4tensor_id(tensor_id) %}
            paddle.static.InputSpec(shape={{shape}}, dtype='{{dtype}}'),
        {%- endfor %}
        ]
        
    instance_ = None
    static_instance_with_cinn_ = None
    static_instance_without_cinn_ = None

{% endmacro %}

{%- macro get_primitive_class_name(op) -%}
PrimitiveOp_{{get_sha_hash_prefix(get_primitive_class_methods(op))}}
{%- endmacro -%}

{% macro get_test_class_methods(op) %}
    def get_test_class(self):
        return {{get_primitive_class_name(op)}}
    def get_inputs(self):
        return [
        {%- for tensor_id in op.tensor_ids %}
        {%- set example_tensor_meta = op.example_input_meta4tensor_id(tensor_id) %}
            {{get_input_tensor_instance(example_tensor_meta)}},
        {%- endfor %}
        ]
{% endmacro %}

{%- macro get_test_class_name(op) -%}
TestPrimitiveOp_{{get_sha_hash_prefix(get_test_class_methods(op))}}
{%- endmacro -%}

need_skip, skip_message = GetNeedSkipAndSkipMessage()
try_run_exit_code, try_run_stderr = GetCurrentStageTryRunExitCodeAndStdErr()

{%- for op in ops %}
{%- if not is_cached_before(get_primitive_class_name(op)) %}
class {{get_primitive_class_name(op)}}(InstanceTrait, paddle.nn.Layer):
    {{get_primitive_class_methods(op)}}
{{cache(get_primitive_class_name(op))}}
{%- endif -%}

@unittest.skipIf(need_skip, skip_message)
class {{get_test_class_name(op)}}(CinnTestBase, unittest.TestCase):
    {{get_test_class_methods(op)}}

    def test_entry(self):
        if AthenaTryRunEnabled():
            if try_run_exit_code == 0:
                # All unittest cases passed.
                return
            if try_run_exit_code < 0:
                # program panicked.
                raise RuntimeError(f"file {__file__} panicked. stderr: \n{try_run_stderr}")
        return self._test_entry()

{% endfor %}

if __name__ == '__main__':
    unittest.main()
