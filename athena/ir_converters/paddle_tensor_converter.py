import athena.ir.ir_type as ir_type
import athena.ir.ir_tensor as ir_tensor
import athena.ir_converters.paddle_type_converter as paddle_type_converter

def ConvertToPaddleTensor(tensor):
  return getattr(PaddleTensorConverter, type(tensor.type).__name__)(tensor)

class PaddleTensorConverter:

  @classmethod
  def DenseTensorType(cls, tensor):
    return ir_tensor.Tensor(
      local_name_prefix=tensor.local_name_prefix,
      name=tensor.name,
      arg_name_as_input=tensor.arg_name_as_input,
      defining_op_name=tensor.defining_op_name,
      type=ir_type.DenseTensorType(
        tensor.shape,
        paddle_type_converter.ConvertTypeToString(tensor.dtype)
      ),
      dim_exprs=tensor.dim_exprs
    )

  @classmethod
  def VectorType(cls, tensor):
    return ir_tensor.Tensor(
      local_name_prefix=tensor.local_name_prefix,
      name=tensor.name,
      arg_name_as_input=tensor.arg_name_as_input,
      defining_op_name=tensor.defining_op_name,
      type=ir_type.VectorType(
        value=[
          ir_type.DenseTensorType(
            t.shape,
            paddle_type_converter.ConvertTypeToString(t.dtype)
          )
          for t in tensor.type.value
        ]
      ),
      dim_exprs=tensor.dim_exprs
    )

  @classmethod
  def NullType(cls, tensor):
    return ir_tensor.Tensor(
      local_name_prefix=tensor.local_name_prefix,
      name=tensor.name,
      arg_name_as_input=tensor.arg_name_as_input,
      defining_op_name=tensor.defining_op_name,
      type=tensor.type,
      dim_exprs=tensor.dim_exprs,
    )
