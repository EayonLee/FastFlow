package com.fastflow.service.workflow;

import cn.hutool.core.util.IdUtil;
import com.fastflow.common.enums.WorkflowType;
import com.fastflow.entity.workflow.node.NodeDefVO;
import com.fastflow.entity.workflow.node.NodeInputDefVO;
import com.fastflow.entity.workflow.node.NodeOutputDefVO;
import org.springframework.stereotype.Service;

import java.util.*;


/**
 * 工作流节点业务逻辑实现类
 * 
 * 主要功能：
 * 1. 负责生成和组装工作流节点的定义信息（NodeDefVO）
 * 2. 包含不同类型节点（UserGuide, WorkflowStart, ChatNode）的构建逻辑
 */
@Service
public class WorkflowNodeService {

    /**
     * 获取所有工作流节点定义列表
     *
     * @return List<NodeDefVO> 包含所有可用节点的定义
     */
    public List<NodeDefVO> getWorkflowNodeList() {
        List<NodeDefVO> nodes = new ArrayList<>();
        nodes.add(createUserGuideNode());
        nodes.add(createWorkflowStartNode());
        nodes.add(createChatNode());
        return nodes;
    }


    /**
     * 系统配置节点
     *
     * @return
     */
    protected NodeDefVO createUserGuideNode() {
        Map<String, Integer> position = new HashMap<>();
        position.put("x", 0);
        position.put("y", 0);

        return NodeDefVO.builder()
                .flowNodeType(WorkflowType.USER_GUIDE.getType())
                .name(WorkflowType.USER_GUIDE.getDescription())
                .icon("⚙️")
                .nodeId(WorkflowType.USER_GUIDE.getType())
                .avatar("/gpt-agent/imgs/workflow/systemConfig.png")
                .version("481")
                .intro("可以配置应用的系统参数")
                .position(position)
                .inputs(Collections.emptyList())
                .outputs(Collections.emptyList())
                .build();
    }

    /**
     * 流程开始节点
     *
     * @return
     */
    protected NodeDefVO createWorkflowStartNode() {
        // Inputs
        List<NodeInputDefVO> inputs = new ArrayList<>();
        inputs.add(NodeInputDefVO.builder()
                .key("userChatInput")
                .valueType("string")
                .label("用户问题")
                .isPro(false)
                .required(true)
                .renderTypeList(Arrays.asList("reference", "textarea"))
                .toolDescription("用户问题")
                .selectedTypeIndex(0)
                .build());

        // Outputs
        List<NodeOutputDefVO> outputs = new ArrayList<>();
        outputs.add(NodeOutputDefVO.builder()
                .id("userChatInput")
                .key("userChatInput")
                .label("用户问题")
                .description("用户问题")
                .type("static")
                .valueType("string")
                .required(false)
                .build());

        Map<String, Integer> position = new HashMap<>();
        position.put("x", 350);
        position.put("y", 0);

        return NodeDefVO.builder()
                .nodeId(IdUtil.objectId())
                .flowNodeType(WorkflowType.WORKFLOW_START.getType())
                .name(WorkflowType.WORKFLOW_START.getDescription())
                .icon("▶️")
                .avatar("/gpt-agent/imgs/workflow/userChatInput.svg")
                .version("481")
                .intro("工作流起点，请从此连线")
                .position(position)
                .inputs(inputs)
                .outputs(outputs)
                .build();
    }

    /**
     * 大模型会话节点
     *
     * @return
     */
    protected NodeDefVO createChatNode() {
        List<NodeInputDefVO> inputs = new ArrayList<>();

        // 1. model
        inputs.add(NodeInputDefVO.builder()
                .key("model")
                .valueType("string")
                .label("模型")
                .isPro(false)
                .renderTypeList(Collections.singletonList("settingLLMModel"))
                .value("360Sec_chat_v1")
                .required(false)
                .llmModelType(null)
                .toolDescription("")
                .debugLabel("")
                .min(null)
                .max(null)
                .step(null)
                .description(null)
                .placeholder(null)
                .customInputConfig(null)
                .canEdit(false)
                .valueDesc("")
                .selectedTypeIndex(0)
                .build());

        // temperature (hidden)
        inputs.add(NodeInputDefVO.builder()
                .key("temperature")
                .valueType("number")
                .renderTypeList(Collections.singletonList("hidden"))
                .value(0.0)
                .build());

        // maxToken (hidden)
        inputs.add(NodeInputDefVO.builder()
                .key("maxToken")
                .valueType("number")
                .renderTypeList(Collections.singletonList("hidden"))
                .value(4000.0)
                .build());

        // isResponseAnswerText (hidden)
        inputs.add(NodeInputDefVO.builder()
                .key("isResponseAnswerText")
                .valueType("boolean")
                .renderTypeList(Collections.singletonList("hidden"))
                .value(true)
                .build());

        // aiChatVision (hidden)
        inputs.add(NodeInputDefVO.builder()
                .key("aiChatVision")
                .valueType("boolean")
                .renderTypeList(Collections.singletonList("hidden"))
                .value(true)
                .build());

        // systemPrompt
        inputs.add(NodeInputDefVO.builder()
                .key("systemPrompt")
                .valueType("string")
                .label("系统提示词")
                .renderTypeList(Arrays.asList("textarea", "reference"))
                .value("")
                .max(3000.0)
                .description("模型固定的引导词，通过调整该内容，可以引导模型的聊天方向。该内容会被固定在上下文的开头，可使用变量，例如{{ip}}")
                .placeholder("模型固定的引导词，通过调整该内容，可以引导模型的聊天方向。该内容会被固定在上下文的开头，可使用变量，例如{{ip}}")
                .build());

        // history
        inputs.add(NodeInputDefVO.builder()
                .key("history")
                .valueType("chatHistory")
                .label("聊天记录")
                .renderTypeList(Arrays.asList("numberInput", "reference"))
                .value(0)
                .required(true)
                .min(0.0)
                .max(50.0)
                .description("最多携带多少轮对话记录")
                .build());

        // stringQuoteText
        inputs.add(NodeInputDefVO.builder()
                .key("stringQuoteText")
                .valueType("any")
                .label("文档引用")
                .renderTypeList(Arrays.asList("reference", "textarea"))
                .debugLabel("文档引用")
                .description("通常用于接受用户上传的文档内容(这需要文档解析)，也可以用于引用其他字符串数据。")
                .build());

        // quoteQA
        inputs.add(NodeInputDefVO.builder()
                .key("quoteQA")
                .valueType("datasetQuote")
                .label("安全知识库引用")
                .renderTypeList(Collections.singletonList("settingDatasetQuotePrompt"))
                .debugLabel("安全知识库引用")
                .value("")
                .build());

        // userChatInput
        inputs.add(NodeInputDefVO.builder()
                .key("userChatInput")
                .valueType("string")
                .label("用户输入")
                .renderTypeList(Arrays.asList("reference", "textarea"))
                .value("")
                .required(true)
                .toolDescription("用户问题")
                .description("用户输入问题")
                .selectedTypeIndex(1)
                .build());

        // Outputs
        List<NodeOutputDefVO> outputs = new ArrayList<>();
        outputs.add(NodeOutputDefVO.builder()
                .id("history")
                .key("history")
                .required(true)
                .label("新的上下文")
                .description("将本次回复内容拼接上历史记录，作为新的上下文返回")
                .valueType("chatHistory")
                .valueDesc("{\n  obj: System | Human | AI;\n  value: string;\n}[]")
                .type("static")
                .build());

        outputs.add(NodeOutputDefVO.builder()
                .id("answerText")
                .key("answerText")
                .required(true)
                .label("AI 恢复内容")
                .description("将在 stream 回复完毕后触发")
                .valueType("string")
                .type("static")
                .build());

        Map<String, Integer> position = new HashMap<>();
        position.put("x", 700);
        position.put("y", 0);

        return NodeDefVO.builder()
                .nodeId(IdUtil.objectId())
                .flowNodeType(WorkflowType.CHAT_NODE.getType())
                .name(WorkflowType.CHAT_NODE.getDescription())
                .icon("🤖")
                .avatar("/gpt-agent/imgs/workflow/ai_chat.svg")
                .version("481")
                .intro("大模型对话节点")
                .position(position)
                .inputs(inputs)
                .outputs(outputs)
                .build();
    }
}
