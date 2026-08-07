import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import SellMate 1.0
import "components"
import "screens"

ApplicationWindow {
    id: window
    visible: true
    title: Theme.businessName
    width: App.windowWidth
    height: App.windowHeight
    color: Theme.background

    readonly property int motionMs: Theme.animationMs
    readonly property bool motionOn: motionMs > 0

    function showToast(title, message) {
        toastTitle.text = title
        toastBody.text = message
        toast.opacity = 1
        toast.visible = true
        toastTimer.restart()
    }

    function hideToast() {
        if (!window.motionOn) {
            toast.visible = false
            toast.opacity = 0
            return
        }
        toastHideAnim.start()
    }

    function screenIndex(name) {
        switch (name) {
        case "boot": return 0
        case "fatal": return 1
        case "attract": return 2
        case "browse": return 3
        case "product_detail": return 4
        case "cart": return 5
        case "payment": return 6
        case "success": return 7
        case "failure": return 8
        default: return 0
        }
    }

    AppShell {
        anchors.fill: parent

        // Layered screens with opacity crossfade (keeps FSM index mapping).
        Item {
            id: stack
            anchors.fill: parent

            property int currentIndex: window.screenIndex(App.screen)

            BootScreen {
                anchors.fill: parent
                opacity: stack.currentIndex === 0 ? 1 : 0
                enabled: stack.currentIndex === 0
                visible: opacity > 0.01
                z: stack.currentIndex === 0 ? 1 : 0
                Behavior on opacity {
                    enabled: window.motionOn
                    NumberAnimation { duration: window.motionMs; easing.type: Easing.OutCubic }
                }
            }
            FatalScreen {
                anchors.fill: parent
                opacity: stack.currentIndex === 1 ? 1 : 0
                enabled: stack.currentIndex === 1
                visible: opacity > 0.01
                z: stack.currentIndex === 1 ? 1 : 0
                Behavior on opacity {
                    enabled: window.motionOn
                    NumberAnimation { duration: window.motionMs; easing.type: Easing.OutCubic }
                }
            }
            AttractScreen {
                anchors.fill: parent
                opacity: stack.currentIndex === 2 ? 1 : 0
                enabled: stack.currentIndex === 2
                visible: opacity > 0.01 || stack.currentIndex === 2
                z: stack.currentIndex === 2 ? 1 : 0
                Behavior on opacity {
                    enabled: window.motionOn
                    NumberAnimation { duration: window.motionMs; easing.type: Easing.OutCubic }
                }
            }
            BrowseScreen {
                anchors.fill: parent
                opacity: stack.currentIndex === 3 ? 1 : 0
                enabled: stack.currentIndex === 3
                visible: opacity > 0.01
                z: stack.currentIndex === 3 ? 1 : 0
                Behavior on opacity {
                    enabled: window.motionOn
                    NumberAnimation { duration: window.motionMs; easing.type: Easing.OutCubic }
                }
            }
            DetailScreen {
                anchors.fill: parent
                opacity: stack.currentIndex === 4 ? 1 : 0
                enabled: stack.currentIndex === 4
                visible: opacity > 0.01
                z: stack.currentIndex === 4 ? 1 : 0
                Behavior on opacity {
                    enabled: window.motionOn
                    NumberAnimation { duration: window.motionMs; easing.type: Easing.OutCubic }
                }
            }
            CartScreen {
                anchors.fill: parent
                opacity: stack.currentIndex === 5 ? 1 : 0
                enabled: stack.currentIndex === 5
                visible: opacity > 0.01
                z: stack.currentIndex === 5 ? 1 : 0
                Behavior on opacity {
                    enabled: window.motionOn
                    NumberAnimation { duration: window.motionMs; easing.type: Easing.OutCubic }
                }
            }
            PaymentScreen {
                anchors.fill: parent
                opacity: stack.currentIndex === 6 ? 1 : 0
                enabled: stack.currentIndex === 6
                visible: opacity > 0.01
                z: stack.currentIndex === 6 ? 1 : 0
                Behavior on opacity {
                    enabled: window.motionOn
                    NumberAnimation { duration: window.motionMs; easing.type: Easing.OutCubic }
                }
            }
            SuccessScreen {
                anchors.fill: parent
                opacity: stack.currentIndex === 7 ? 1 : 0
                enabled: stack.currentIndex === 7
                visible: opacity > 0.01
                z: stack.currentIndex === 7 ? 1 : 0
                Behavior on opacity {
                    enabled: window.motionOn
                    NumberAnimation { duration: window.motionMs; easing.type: Easing.OutCubic }
                }
            }
            FailureScreen {
                anchors.fill: parent
                opacity: stack.currentIndex === 8 ? 1 : 0
                enabled: stack.currentIndex === 8
                visible: opacity > 0.01
                z: stack.currentIndex === 8 ? 1 : 0
                Behavior on opacity {
                    enabled: window.motionOn
                    NumberAnimation { duration: window.motionMs; easing.type: Easing.OutCubic }
                }
            }
        }
    }

    ElevatedCard {
        id: toast
        visible: false
        opacity: 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.pageMargin
        height: toastCol.implicitHeight + 32
        z: 100

        Behavior on opacity {
            enabled: window.motionOn
            NumberAnimation { duration: Math.max(120, window.motionMs); easing.type: Easing.OutCubic }
        }

        NumberAnimation {
            id: toastHideAnim
            target: toast
            property: "opacity"
            to: 0
            duration: window.motionOn ? Math.max(120, window.motionMs) : 0
            easing.type: Easing.InCubic
            onStopped: {
                toast.visible = false
            }
        }

        Column {
            id: toastCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 18
            spacing: 6
            Text {
                id: toastTitle
                width: parent.width
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.subtitleFontPx - 2
                font.bold: true
                wrapMode: Text.WordWrap
            }
            Text {
                id: toastBody
                width: parent.width
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodyFontPx
                wrapMode: Text.WordWrap
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: window.hideToast()
        }
    }

    Timer {
        id: toastTimer
        interval: 4000
        onTriggered: window.hideToast()
    }

    MouseArea {
        anchors.fill: parent
        z: -10
        acceptedButtons: Qt.AllButtons
        propagateComposedEvents: true
        onPressed: function(mouse) {
            App.bumpIdle()
            mouse.accepted = false
        }
    }

    Shortcut {
        sequence: "Esc"
        onActivated: {
            if (window.visibility !== Window.FullScreen)
                Qt.quit()
        }
    }
}
