import os
os.environ['FLAGS_cinn_new_group_scheduler'] = '1'
os.environ['FLAGS_group_schedule_tiling_first'] = '1'
os.environ['FLAGS_prim_all'] = 'true'
os.environ['FLAGS_prim_enable_dynamic'] = '1'
os.environ['FLAGS_enable_pir_api'] = '1'
os.environ['FLAGS_cinn_bucket_compile'] = '1'

import unittest
import numpy as np
import paddle

def NumCurrentUnittestOperations():
    return {{(stmts | length)}} # number-of-ops

def GetPaddleDebugNumAllowedOps():
    try:
        return int(os.getenv('PADDLE_DEBUG_NUM_ALLOWED_OPS'))
    except:
        return None

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
    return enable_cinn not in {
        "0",
        "False",
        "false",
        "OFF",
    }


paddle_debug_num_allowed_ops = GetPaddleDebugNumAllowedOps()

if type(paddle_debug_num_allowed_ops) is not int:
    def EarlyReturn(i):
        return False
else:
    def EarlyReturn(i):
        return i >= paddle_debug_num_allowed_ops

class {{unittest_class_name}}(paddle.nn.Layer):
    def __init__(self):
        super().__init__()

    def forward(self, {{ input_arg_names | join(", ") }}):
        args = [{{stmts[0].op_func_in_out_names_signature.in_names | join(", ")}}]
        for op_idx, op_func in enumerate(self.get_op_funcs()):
            if EarlyReturn(op_idx):
                return args
            args = op_func(*args)
        return args

    def get_op_funcs(self):
        return [
        {%- for stmt in stmts %}
            self.{{stmt.op_unique_local_name}},
        {%- endfor %}
        ]

    {%- for stmt in stmts %}
    {%- set op_idx = loop.index0 %}

    def {{stmt.op_unique_local_name}}(self, {{stmt.op_func_in_out_names_signature.in_names | join(", ")}}):

        # EarlyReturn({{op_idx}})
    
        #    op: {{stmt.op_name}}
        #  type: ({{stmt.outputs_type_strs|join(", ")}}) <- ({{stmt.inputs_type_strs|join(", ")}})
        # shape: ({{stmt.outputs_shape_symbol_strs|join(", ")}}) <- ({{stmt.inputs_shape_symbol_strs|join(", ")}})
        #  data: ({{stmt.outputs_data_symbol_strs|join(", ")}}) <- ({{stmt.inputs_data_symbol_strs|join(", ")}})

        {%- for pycode in stmt.pycode %}
        {%- if pycode.num_tabs == 0 %}
        {{pycode.pycode}}
        {%- elif pycode.num_tabs == 1 %}
            {{pycode.pycode}}
        {%- elif pycode.num_tabs == 2 %}
                {{pycode.pycode}}
        {%- else %}
        raise NotImplementedError("unsupported indent size {{pycode.num_tabs}}")
        {%- endif %}
        {%- endfor %}

        return [{{stmt.op_func_in_out_names_signature.out_names | join(", ")}}]
    
    {%- endfor %}


class Test{{unittest_class_name}}(unittest.TestCase):
    def setUp(self):
        paddle.seed(2024)
        self.prepare_data()

    def prepare_data(self):
        self.inputs = [
        {%- for shape, dtype, big_dtype, data, min, max in input_tensor_descs %}
        {%- if data != None %}
            paddle.to_tensor({{data}}, dtype='{{dtype}}').reshape({{shape}}),
        {%- elif big_dtype == "bool" %}
            paddle.zeros({{shape}}, dtype='{{dtype}}'),
        {%- elif big_dtype == "int64" %}
            paddle.randint(low={{min}}, high={{max}}, shape={{shape}}, dtype='{{dtype}}'),
        {%- elif big_dtype == "float64" %}
            paddle.uniform({{shape}}, dtype='{{dtype}}', min={{min}}, max={{max}}),
        {%- endif %}
        {%- endfor %}
        ]
        for input in self.inputs:
          input.stop_gradient = True

    def apply_to_static(self, net, use_cinn):
        build_strategy = paddle.static.BuildStrategy()
        input_spec = [
        {%- for shape, dtype in input_spec_shape_dtypes %}
            paddle.static.InputSpec(shape={{shape}}, dtype='{{dtype}}'),
        {%- endfor %}
        ]
        build_strategy.build_cinn_pass = use_cinn
        return paddle.jit.to_static(
            net,
            input_spec=input_spec,
            build_strategy=build_strategy,
            full_graph=True,
        )

    def train(self, use_cinn):
        net = {{unittest_class_name}}()
        net.eval()
        if GetEnvVarEnableJit():
            net = self.apply_to_static(net, use_cinn)
        out = net(*self.inputs)
        return out

    def test_train(self):
        dy_outs = self.train(use_cinn=False)
        cinn_outs = self.train(use_cinn=GetEnvVarEnableCinn())

        for cinn_out, dy_out in zip(cinn_outs, dy_outs):
          if type(cinn_out) is list and type(dy_out) is list:
            for x, y in zip(cinn_out, dy_out):
              self.assert_all_close(x, y)
          else:
            self.assert_all_close(cinn_out, dy_out)

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

if __name__ == '__main__':
    unittest.main()
