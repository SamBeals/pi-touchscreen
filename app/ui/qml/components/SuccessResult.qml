import QtQuick
import QtQuick.Layouts
import SellMate 1.0

ColumnLayout {
    id: root
    property string message: ""
    spacing: Theme.sectionGap
    anchors.fill: parent

    readonly property bool active: App.screen === "success"

    Item { Layout.fillHeight: true }

    Item {
        Layout.alignment: Qt.AlignHCenter
        width: Theme.statusBadgeSize
        height: Theme.statusBadgeSize

        Rectangle {
            id: badge
            anchors.fill: parent
            radius: width / 2
            color: Theme.primary
            scale: root.active ? 1 : 0.72
            opacity: root.active ? 1 : 0

            Behavior on scale {
                NumberAnimation {
                    duration: Math.max(160, Theme.animationMs)
                    easing.type: Easing.OutBack
                }
            }
            Behavior on opacity {
                NumberAnimation { duration: Math.max(120, Theme.animationMs) }
            }

            // Soft ring
            Rectangle {
                anchors.centerIn: parent
                width: parent.width + 18
                height: parent.height + 18
                radius: width / 2
                color: "transparent"
                border.width: 3
                border.color: Theme.primary
                opacity: 0.28
            }

            Text {
                anchors.centerIn: parent
                text: "✓"
                color: Theme.text
                font.family: Theme.fontFamily
                font.pixelSize: Theme.statusBadgeSize * 0.48
                font.bold: true
            }
        }
    }

    Text {
        text: "Purchase complete"
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
