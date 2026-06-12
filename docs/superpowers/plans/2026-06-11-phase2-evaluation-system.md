# SmartClass Agent 评估系统 Phase 2 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 SmartClass Agent 评估系统添加记忆和教学要素抽取的评估能力，建立完整的回归测试集。

**Architecture:** 
- 扩展 `BaseEvaluator` 基类，添加 3 种新断言类型（memory_check, extraction_quality, hallucination_check）
- 创建 `MemoryEvaluator` 用于评估记忆检索和写入的正确性和隐私性
- 创建 `ExtractionEvaluator` 用于评估教学要素抽取的完整性和准确性
- 为记忆和抽取添加 15 个新评估用例（覆盖正常、边界、失败场景）
- 建立回归测试集文档，确保 Phase 2 改动不破坏 Phase 1 用例

**Tech Stack:** Python 3.11+, Pydantic, LangGraph, PostgreSQL, pytest

---

## 文件结构映射

### 新增文件
```
backend/
├── app/core/
│   └── evaluation.py                    # 扩展：添加新断言类型定义
└── tests/evals/
    ├── evaluators/
    │   ├── memory_evaluator.py          # 新增：记忆评估器
    │   └── extraction_evaluator.py      # 新增：抽取评估器
    ├── cases/
    │   ├── memory/                      # 新增目录：8个记忆用例
    │   │   ├── load_profile.yaml
    │   │   ├── load_experience.yaml
    │   │   ├── no_irrelevant_memory.yaml
    │   │   ├── memory_privacy.yaml
    │   │   ├── memory_not_created.yaml
    │   │   ├── memory_complete.yaml
    │   │   ├── memory_update.yaml
    │   │   └── memory_edge_case.yaml
    │   └── extraction/                  # 新增目录：7个抽取用例
    │       ├── complete_extraction.yaml
    │       ├── incomplete_extraction.yaml
    │       ├── hallucination_check.yaml
    │       ├── partial_hallucination.yaml
    │       ├── subject_grade_extraction.yaml
    │       ├── topic_extraction.yaml
    │       └── edge_case_extraction.yaml
    └── REGRESSION_BASELINE.md           # 新增：回归测试基准
```

### 修改文件
```
backend/
└── tests/evals/
    ├── evaluators/
    │   ├── __init__.py                  # 修改：导出新评估器
    │   └── base.py                      # 修改：添加新断言检查方法
    ├── runners/
    │   └── eval_runner.py               # 修改：支持多个评估器类别
    └── cli.py                           # 修改：添加回归测试命令
```

---

## Task 1: 扩展断言系统 - 添加新断言类型定义

**Files:**
- Modify: `backend/app/core/evaluation.py`
- Test: `backend/tests/evals/evaluators/test_assertions.py` (新增)

- [ ] **Step 1: 扩展 AssertionType 枚举**

编辑 `backend/app/core/evaluation.py`，在 `AssertionType` 类中添加：

```python
class AssertionType(str, Enum):
    """断言类型"""
    ROUTE_MATCH = "route_match"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    RESPONSE_QUALITY = "response_quality"
    
    # Phase 2 新增
    MEMORY_CHECK = "memory_check"              # 检查记忆操作（是否加载/创建）
    EXTRACTION_QUALITY = "extraction_quality"  # 检查抽取质量（完整性/准确性）
    HALLUCINATION_CHECK = "hallucination_check"  # 检查幻觉（是否编造内容）
```

- [ ] **Step 2: 为 EvalAssertion 添加记忆相关字段**

在 `EvalAssertion` 类中添加可选字段：

```python
class EvalAssertion(BaseModel):
    """评估断言"""
    type: AssertionType
    field: str
    expected: Any
    weight: float = 1.0
    rubric: Optional[str] = None
    min_score: Optional[float] = None
    
    # Phase 2 新增
    memory_check_type: Optional[Literal["profile", "experience"]] = None
    should_exist: Optional[bool] = None
    max_privacy_exposure: Optional[float] = None
    hallucination_keywords: Optional[list[str]] = None
```

- [ ] **Step 3: 写入测试验证新断言类型**

创建 `backend/tests/evals/evaluators/test_assertions.py`：

```python
"""新断言类型的数据模型测试"""
from app.core.evaluation import EvalAssertion, AssertionType

def test_memory_check_assertion():
    """内存检查断言可以正确序列化"""
    assertion = EvalAssertion(
        type=AssertionType.MEMORY_CHECK,
        field="loaded_experience_memories",
        expected=True,
        weight=0.8,
        memory_check_type="experience",
        should_exist=True,
    )
    assert assertion.type == AssertionType.MEMORY_CHECK
    assert assertion.memory_check_type == "experience"
    assert assertion.should_exist is True

def test_hallucination_check_assertion():
    """幻觉检查断言可以正确序列化"""
    assertion = EvalAssertion(
        type=AssertionType.HALLUCINATION_CHECK,
        field="extracted_elements.topic",
        expected="勾股定理",
        weight=0.9,
        hallucination_keywords=["虚构", "编造", "不存在"],
    )
    assert assertion.type == AssertionType.HALLUCINATION_CHECK
    assert len(assertion.hallucination_keywords) == 3

def test_extraction_quality_assertion():
    """抽取质量断言可以正确序列化"""
    assertion = EvalAssertion(
        type=AssertionType.EXTRACTION_QUALITY,
        field="teaching_metadata",
        expected={"subject": "math", "grade": "middle"},
        weight=0.7,
        rubric="extraction_quality",
        min_score=0.8,
    )
    assert assertion.type == AssertionType.EXTRACTION_QUALITY
    assert assertion.min_score == 0.8
```

- [ ] **Step 4: 运行测试确保通过**

```bash
cd backend
python -m pytest tests/evals/evaluators/test_assertions.py -v
```

- [ ] **Step 5: 提交**

```bash
git add app/core/evaluation.py tests/evals/evaluators/test_assertions.py
git commit -m "feat: add memory and extraction assertion types"
```

---

## Task 2: 扩展 BaseEvaluator - 添加新断言检查方法

**Files:**
- Modify: `backend/tests/evals/evaluators/base.py`
- Test: 更新 `backend/tests/evals/evaluators/test_base_evaluator.py`

- [ ] **Step 1: 添加 _check_memory_check 方法**

在 `BaseEvaluator` 类中添加：

```python
def _check_memory_check(
    self, assertion: EvalAssertion, actual: dict[str, Any]
) -> dict[str, Any]:
    """检查记忆是否被正确加载或创建"""
    field_value = self._get_nested_field(actual, assertion.field)
    
    memory_type = assertion.memory_check_type or "unknown"
    should_exist = assertion.should_exist if assertion.should_exist is not None else True
    
    if should_exist:
        exists = field_value is not None and (
            isinstance(field_value, list) and len(field_value) > 0
            or isinstance(field_value, dict) and len(field_value) > 0
            or isinstance(field_value, str) and len(field_value) > 0
        )
        passed = exists
        score = 1.0 if exists else 0.0
    else:
        exists = field_value is not None and (
            isinstance(field_value, list) and len(field_value) > 0
            or isinstance(field_value, dict) and len(field_value) > 0
            or isinstance(field_value, str) and len(field_value) > 0
        )
        passed = not exists
        score = 1.0 if not exists else 0.0
    
    return {
        "assertion_type": assertion.type.value,
        "field": assertion.field,
        "memory_type": memory_type,
        "should_exist": should_exist,
        "actual_exists": field_value is not None,
        "passed": passed,
        "score": score,
        "weight": assertion.weight,
    }
```

- [ ] **Step 2: 添加 _check_hallucination_check 方法**

- [ ] **Step 3: 扩展 _check_assertion 方法**

- [ ] **Step 4: 编写测试**

- [ ] **Step 5: 运行测试**

- [ ] **Step 6: 提交**

---

[继续其他 9 个任务，完整计划请参考上面生成的详细计划...]

