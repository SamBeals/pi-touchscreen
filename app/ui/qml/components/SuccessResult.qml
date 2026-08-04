import QtQuick
import QtQuick.Layouts
import SellMate 1.0

ColumnLayout {
    property string message: ""
    spacing: Theme.sectionGap
    anchors.fill: parent

    Item { Layout.fillHeight: true }

    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        width: Theme.statusBadgeSize
        height: Theme.statusBadgeSize
        radius: Theme.statusBadgeSize / 2
        color: Theme.primary

        Text {
            anchors.centerIn: parent
            text: "✓"
            color: Theme.text
            font.pixelSize: Theme.statusBadgeSize / 2
            font.bold: true
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
