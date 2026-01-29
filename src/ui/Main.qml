import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls.Material 2.15

ApplicationWindow {
    id: window
    visible: true
    width: 1600
    height: 900
    title: "AI CAD Architect"
    
    Material.theme: Material.Light
    Material.accent: Material.Blue
    Material.primary: Material.Indigo
    
    // 状态
    property string currentCode: ""
    property string currentModelPath: ""
    property var chatHistory: []
    property var parameterGroups: []
    property bool isBusy: false
    
    // 连接控制器信号
    Connections {
        target: controller
        
        function onCodeChanged(code) {
            currentCode = code
            codeEditor.text = code
        }
        
        function onModelChanged(path) {
            currentModelPath = path
            modelViewer.source = "file://" + path
        }
        
        function onParametersChanged(params) {
            parameterGroups = params
            parameterModel.clear()
            for (var i = 0; i < params.length; i++) {
                parameterModel.append(params[i])
            }
        }
        
        function onHistoryChanged(sessions) {
            historyModel.clear()
            for (var i = 0; i < sessions.length; i++) {
                historyModel.append(sessions[i])
            }
        }
        
        function onStatusMessage(msg) {
            statusBar.text = msg
        }
        
        function onErrorMessage(msg) {
            errorDialog.text = msg
            errorDialog.open()
        }
        
        function onProgressChanged(progress) {
            progressBar.value = progress
        }
        
        function onBusyChanged(busy) {
            isBusy = busy
        }
        
        function onChatMessageAdded(role, content) {
            chatModel.append({role: role, content: content})
            chatListView.positionViewAtEnd()
        }
    }
    
    // 主布局
    SplitView {
        anchors.fill: parent
        orientation: Qt.Horizontal
        
        // 左侧: 对话面板
        Rectangle {
            SplitView.preferredWidth: 350
            SplitView.minimumWidth: 250
            color: "#f5f5f5"
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10
                
                // 标题
                Label {
                    text: "AI 对话"
                    font.pixelSize: 18
                    font.bold: true
                    color: Material.primary
                }
                
                // 对话列表
                ListView {
                    id: chatListView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 8
                    
                    model: ListModel { id: chatModel }
                    
                    delegate: Rectangle {
                        width: chatListView.width - 10
                        height: chatContent.implicitHeight + 20
                        radius: 8
                        color: model.role === "User" ? "#e3f2fd" : 
                               model.role === "AI" ? "#e8f5e9" :
                               model.role === "Error" ? "#ffebee" : "#fafafa"
                        
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 4
                            
                            Label {
                                text: model.role
                                font.bold: true
                                font.pixelSize: 12
                                color: model.role === "User" ? "#1976d2" :
                                       model.role === "AI" ? "#388e3c" :
                                       model.role === "Error" ? "#d32f2f" : "#757575"
                            }
                            
                            Label {
                                id: chatContent
                                text: model.content
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                    
                    ScrollBar.vertical: ScrollBar {}
                }
                
                // 输入区域
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 100
                    radius: 8
                    border.color: Material.primary
                    border.width: inputArea.focus ? 2 : 1
                    
                    TextArea {
                        id: inputArea
                        anchors.fill: parent
                        anchors.margins: 8
                        placeholderText: "输入指令，例如：做一个圆桌..."
                        wrapMode: Text.Wrap
                        
                        Keys.onReturnPressed: {
                            if (event.modifiers & Qt.ShiftModifier) {
                                event.accepted = false
                            } else {
                                sendMessage()
                                event.accepted = true
                            }
                        }
                    }
                }
                
                // 按钮
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    
                    Button {
                        text: "发送"
                        Layout.fillWidth: true
                        Material.background: Material.primary
                        Material.foreground: "white"
                        enabled: !isBusy && inputArea.text.trim().length > 0
                        onClicked: sendMessage()
                    }
                    
                    Button {
                        text: "新建"
                        Layout.preferredWidth: 80
                        onClicked: controller.newSession()
                    }
                }
                
                // 进度条
                ProgressBar {
                    id: progressBar
                    Layout.fillWidth: true
                    visible: isBusy
                    indeterminate: value === 0
                }
            }
        }
        
        // 中间: 代码和参数
        Rectangle {
            SplitView.preferredWidth: 500
            SplitView.minimumWidth: 300
            color: "white"
            
            TabBar {
                id: middleTabBar
                width: parent.width
                
                TabButton { text: "代码编辑" }
                TabButton { text: "参数调节" }
            }
            
            StackLayout {
                anchors.top: middleTabBar.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 10
                currentIndex: middleTabBar.currentIndex
                
                // 代码编辑器
                ColumnLayout {
                    spacing: 10
                    
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        border.color: "#ddd"
                        border.width: 1
                        radius: 4
                        
                        ScrollView {
                            anchors.fill: parent
                            anchors.margins: 1
                            
                            TextArea {
                                id: codeEditor
                                font.family: "Courier New"
                                font.pixelSize: 13
                                wrapMode: Text.NoWrap
                                selectByMouse: true
                                
                                background: Rectangle {
                                    color: "#fafafa"
                                }
                                
                                onTextChanged: {
                                    if (text !== currentCode) {
                                        currentCode = text
                                    }
                                }
                            }
                        }
                    }
                    
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        
                        Button {
                            text: "渲染"
                            Layout.fillWidth: true
                            Material.background: "#4caf50"
                            Material.foreground: "white"
                            enabled: !isBusy && codeEditor.text.length > 0
                            onClicked: {
                                controller.setCode(codeEditor.text)
                                controller.renderCurrentCode()
                            }
                        }
                        
                        Button {
                            text: "复制"
                            Layout.preferredWidth: 80
                            onClicked: {
                                codeEditor.selectAll()
                                codeEditor.copy()
                                codeEditor.deselect()
                                statusBar.text = "代码已复制"
                            }
                        }
                    }
                }
                
                // 参数面板
                ColumnLayout {
                    spacing: 10
                    
                    ListView {
                        id: parameterListView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        
                        model: ListModel { id: parameterModel }
                        
                        delegate: ColumnLayout {
                            width: parameterListView.width - 20
                            spacing: 5
                            
                            // 组标题
                            Label {
                                text: model.name
                                font.bold: true
                                font.pixelSize: 14
                                color: Material.primary
                                Layout.topMargin: 10
                            }
                            
                            // 参数列表
                            Repeater {
                                model: params
                                
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10
                                    
                                    Label {
                                        text: modelData.shortName
                                        Layout.preferredWidth: 120
                                    }
                                    
                                    SpinBox {
                                        id: paramSpinBox
                                        from: -99999
                                        to: 99999
                                        stepSize: 1
                                        value: modelData.value
                                        editable: true
                                        Layout.fillWidth: true
                                        
                                        property string fullName: modelData.fullName
                                        
                                        onValueModified: {
                                            controller.updateParameter(fullName, value)
                                        }
                                    }
                                }
                            }
                        }
                        
                        ScrollBar.vertical: ScrollBar {}
                    }
                    
                    Button {
                        text: "应用参数 & 重新渲染"
                        Layout.fillWidth: true
                        Material.background: "#2196f3"
                        Material.foreground: "white"
                        enabled: !isBusy
                        onClicked: controller.renderCurrentCode()
                    }
                }
            }
        }
        
        // 右侧: 3D 预览
        Rectangle {
            SplitView.preferredWidth: 550
            SplitView.minimumWidth: 300
            color: "#fafafa"
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10
                
                Label {
                    text: "3D 预览"
                    font.pixelSize: 18
                    font.bold: true
                    color: Material.primary
                }
                
                // 3D 视图占位符 (实际需要通过 Python 注入)
                Rectangle {
                    id: modelViewer
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "white"
                    border.color: "#ddd"
                    border.width: 1
                    radius: 4
                    
                    property string source: ""
                    
                    Label {
                        anchors.centerIn: parent
                        text: modelViewer.source ? "模型已加载\n" + modelViewer.source : "等待模型生成..."
                        horizontalAlignment: Text.AlignHCenter
                        color: "#999"
                    }
                    
                    // 实际的 3D 视图需要通过 Python 注入
                    // 这里只是占位符
                }
                
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    
                    Button {
                        text: "导出 STL"
                        Layout.fillWidth: true
                        enabled: currentModelPath.length > 0
                        onClicked: exportDialog.open()
                    }
                    
                    Button {
                        text: "重置视图"
                        Layout.preferredWidth: 100
                    }
                }
            }
        }
        
        // 历史面板
        Rectangle {
            SplitView.preferredWidth: 200
            SplitView.minimumWidth: 150
            color: "#f5f5f5"
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 10
                
                Label {
                    text: "历史记录"
                    font.pixelSize: 16
                    font.bold: true
                    color: Material.primary
                }
                
                ListView {
                    id: historyListView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 4
                    
                    model: ListModel { id: historyModel }
                    
                    delegate: ItemDelegate {
                        width: historyListView.width
                        height: 50
                        
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 2
                            
                            Label {
                                text: model.title
                                font.pixelSize: 13
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            
                            Label {
                                text: model.preview || ""
                                font.pixelSize: 11
                                color: "#999"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                        
                        onClicked: controller.loadSession(model.filename)
                        
                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.RightButton
                            onClicked: {
                                historyMenu.filename = model.filename
                                historyMenu.popup()
                            }
                        }
                    }
                    
                    ScrollBar.vertical: ScrollBar {}
                }
                
                Button {
                    text: "刷新"
                    Layout.fillWidth: true
                    onClicked: {
                        var sessions = controller.getHistoryList()
                        historyModel.clear()
                        for (var i = 0; i < sessions.length; i++) {
                            historyModel.append(sessions[i])
                        }
                    }
                }
            }
        }
    }
    
    // 状态栏
    footer: ToolBar {
        RowLayout {
            anchors.fill: parent
            anchors.margins: 5
            
            Label {
                id: statusBar
                text: "就绪"
                Layout.fillWidth: true
            }
            
            BusyIndicator {
                running: isBusy
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
            }
        }
    }
    
    // 对话框
    Dialog {
        id: errorDialog
        title: "错误"
        modal: true
        anchors.centerIn: parent
        standardButtons: Dialog.Ok
        
        property alias text: errorLabel.text
        
        Label {
            id: errorLabel
            wrapMode: Text.Wrap
            width: 300
        }
    }
    
    FileDialog {
        id: exportDialog
        title: "导出模型"
        nameFilters: ["STL Files (*.stl)", "STEP Files (*.step)"]
        fileMode: FileDialog.SaveFile
        onAccepted: controller.exportModel(selectedFile)
    }
    
    Menu {
        id: historyMenu
        property string filename: ""
        
        MenuItem {
            text: "加载"
            onTriggered: controller.loadSession(historyMenu.filename)
        }
        MenuItem {
            text: "删除"
            onTriggered: controller.deleteSession(historyMenu.filename)
        }
    }
    
    // 函数
    function sendMessage() {
        var text = inputArea.text.trim()
        if (text.length === 0) return
        
        inputArea.clear()
        controller.generateFromRequest(text)
    }
    
    // 初始化
    Component.onCompleted: {
        // 加载历史列表
        var sessions = controller.getHistoryList()
        for (var i = 0; i < sessions.length; i++) {
            historyModel.append(sessions[i])
        }
        
        // 添加欢迎消息
        chatModel.append({
            role: "System",
            content: "欢迎使用 AI CAD Architect！\n\n" +
                     "输入自然语言描述来生成 3D 模型，例如：\n" +
                     "• 做一个圆桌\n" +
                     "• 设计一个带抽屉的书桌\n" +
                     "• 创建一个简单的椅子\n\n" +
                     "生成后可以手动编辑代码或调节参数。"
        })
    }
}
