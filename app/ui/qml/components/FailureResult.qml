import QtQuick
import QtQuick.Layouts
import SellMate 1.0

ColumnLayout {
    id: root
    property string message: ""
    spacing: Theme.sectionGap
    anchors.fill: parent

    readonly property bool active: App.screen === "failure"

    Item { Layout.fillHeight: true }

    Item {
        Layout.alignment: Qt.AlignHCenter
        width: Theme.statusBadgeSize
        height: Theme.statusBadgeSize

        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: Theme.errorSurface
            scale: root.active ? 1 : 0.85
            Behavior on scale {
                NumberAnimation {
                    duration: Math.max(140, Theme.animationMs)
                    easing.type: Easing.OutCubic
                }
            }

            Text {
                anchors.centerIn: parent
                text: "!"
                color: Theme.error
                font.family: Theme.fontFamily
                font.pixelSize: Theme.statusBadgeSize * 0.48
                font.bold: true
            }
        }
    }

    Text {
        text: "Something went wrong"
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.titleFontPx
        font.bold: true
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        Layout.fillWidth: true
    }

    Text {
        text: message
        color: Theme.textMuted
        font.family: Theme.fontFamily
        font.pixelSize: Theme.subtitleFontPx
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        Layout.fillWidth: true
        visible: message.length > 0
    }

    Item { Layout.fillHeight: true }

    PrimaryButton {
        text: "Done"
        Layout.fillWidth: true
        onClicked: App.finishToAttract()
    }
}
