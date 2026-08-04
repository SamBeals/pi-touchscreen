import QtQuick
import QtQuick.Layouts

ColumnLayout {
    property string message: ""
    spacing: Theme.sectionGap
    anchors.fill: parent

    Item { Layout.fillHeight: true }

    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        width: 72
        height: 72
        radius: 36
        color: "#FEE2E2"

        Text {
            anchors.centerIn: parent
            text: "!"
            color: Theme.error
            font.pixelSize: 36
            font.bold: true
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
