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

    function showToast(title, message) {
        toastTitle.text = title
        toastBody.text = message
        toast.visible = true
        toastTimer.restart()
    }

    AppShell {
        anchors.fill: parent

        StackLayout {
            id: stack
            anchors.fill: parent
            currentIndex: {
                switch (App.screen) {
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

            BootScreen {}
            FatalScreen {}
            AttractScreen {}
            BrowseScreen {}
            DetailScreen {}
            CartScreen {}
            PaymentScreen {}
            SuccessScreen {}
            FailureScreen {}
        }
    }

    ElevatedCard {
        id: toast
        visible: false
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.pageMargin
        height: toastCol.implicitHeight + 32
        z: 100

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
            onClicked: toast.visible = false
        }
    }

    Timer {
        id: toastTimer
        interval: 4000
        onTriggered: toast.visible = false
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
