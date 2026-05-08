use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyFloat, PyList};
use std::collections::BTreeMap;
use vrl::value::Value;

use vrl::prelude::*;

#[pyclass]
pub struct VrlValue {
    pub inner: Value,
}

impl VrlValue {
    pub fn new(value: Value) -> Self {
        VrlValue { inner: value }
    }

    pub fn into_py_object(self, py: Python<'_>) -> PyResult<PyObject> {
        match self.inner {
            Value::Array(arr) => {
                let list = PyList::empty_bound(py);
                for val in arr {
                    list.append(VrlValue::new(val).into_py_object(py)?)?;
                }
                Ok(list.into_py(py))
            }
            Value::Bytes(b) => Ok(String::from_utf8_lossy(&b).into_py(py)),
            Value::Boolean(b) => Ok(b.into_py(py)),
            Value::Float(f) => Ok(PyFloat::new_bound(py, f.into_inner()).into_py(py)),
            Value::Integer(i) => Ok(i.into_py(py)),
            Value::Null => Ok(py.None()),
            Value::Object(map) => {
                let dict = PyDict::new_bound(py);
                for (k, v) in map {
                    dict.set_item(k.as_str(), VrlValue::new(v).into_py_object(py)?)?;
                }
                Ok(dict.into_py(py))
            }
            Value::Timestamp(ts) => Ok(ts.to_rfc3339().into_py(py)),
            _ => Ok(py.None()),
        }
    }
}

impl<'py> FromPyObject<'py> for VrlValue {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let type_name_owned = ob.get_type().name()?.to_string();
        let val: Value = match type_name_owned.as_str() {
            "bool" => Value::Boolean(ob.extract::<bool>()?),
            "bytes" => Value::Bytes(ob.extract::<Vec<u8>>()?.into()),
            "dict" => {
                let dict = ob.downcast::<PyDict>()?;
                let mut map = BTreeMap::new();
                for (k, v) in dict.iter() {
                    let key: String = k.extract()?;
                    let value: VrlValue = v.extract()?;
                    map.insert(key.into(), value.inner);
                }
                Value::Object(map)
            }
            "float" => Value::Float(
                NotNan::new(ob.extract::<f64>()?).map_err(|_| {
                    PyErr::new::<PyValueError, _>("Provided float value is NaN")
                })?,
            ),
            "int" => Value::Integer(ob.extract::<i64>()?),
            "list" => {
                let list = ob.downcast::<PyList>()?;
                let mut vec = Vec::new();
                for item in list.iter() {
                    let value: VrlValue = item.extract()?;
                    vec.push(value.inner);
                }
                Value::Array(vec)
            }
            "NoneType" => Value::Null,
            "str" => Value::Bytes(ob.extract::<String>()?.into()),
            _ => return Err(PyTypeError::new_err("Unsupported type")),
        };

        Ok(VrlValue::new(val))
    }
}
